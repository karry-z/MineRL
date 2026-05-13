from __future__ import annotations

from collections import deque
import locale
import logging
import os
import signal
import socket
import struct
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import psutil

from minerl.protocol.mission import MALMO_VERSION, build_mission_init
from minerl.protocol.wire import recv_message, send_message
from minerl.runtime.assets import find_minecraft_dir
from minerl.runtime.backend import BackendError, BackendFrame

SOCKET_TIMEOUT = 60.0
LAUNCH_TIMEOUT = 180.0
STDOUT_TAIL_LINES = 200

logger = logging.getLogger(__name__)


class MinecraftBackend:
    """Subprocess/socket backend for the existing Minecraft/Malmo runtime."""

    def __init__(
        self,
        *,
        minecraft_dir: str | os.PathLike[str] | None = None,
        base_port: int = 9000,
        max_mem: str = "4G",
        socket_timeout: float | None = None,
    ) -> None:
        self.minecraft_dir = Path(minecraft_dir) if minecraft_dir else find_minecraft_dir()
        self.base_port = base_port
        self.max_mem = max_mem
        self.socket_timeout = (
            socket_timeout
            if socket_timeout is not None
            else float(os.environ.get("MINERL_SOCKET_TIMEOUT", SOCKET_TIMEOUT))
        )
        self.process: psutil.Popen | None = None
        self.sock: socket.socket | None = None
        self.port: int | None = None
        self.process_group_id: int | None = None
        self.run_dir: tempfile.TemporaryDirectory[str] | None = None
        self.phase = "idle"
        self.current_task_id: str | None = None
        self.stdout_tail: deque[str] = deque(maxlen=STDOUT_TAIL_LINES)
        self._stdout_condition = threading.Condition()
        self._stdout_thread: threading.Thread | None = None
        self._stdout_ready = False
        self._stdout_selected_port: int | None = None
        self._stdout_counter = 0

    def reset(self, task, *, seed: int | None, options: dict[str, Any]) -> BackendFrame:
        self.current_task_id = task.id
        started = time.monotonic()
        logger.info(f"Starting Minecraft reset for {task.id} with seed {seed}.")
        try:
            self._phase("ensure_process")
            self._ensure_process(seed=seed)
            self._connect()
            self._quit_current_episode()

            episode_id = str(uuid.uuid4())
            mission = build_mission_init(task.to_mission_xml(), episode_id=episode_id)
            token = f"{episode_id}:0:0:1:true"
            if seed is not None:
                token += f":{seed}"

            self._phase("mission_send")
            logger.debug(
                f"Sending mission {episode_id} for {task.id}; XML payload is {len(mission)} bytes."
            )
            send_message(self.sock, mission)
            send_message(self.sock, token.encode("utf-8"))
            self._phase("mission_ack")
            ok_reply = recv_message(self.sock)
            (ok,) = struct.unpack("!I", ok_reply)
            logger.debug(f"Minecraft returned mission acknowledgement {ok} for {task.id}.")
            if ok != 1:
                raise BackendError(f"Minecraft rejected mission init with code {ok}")

            frame = self._peek()
            logger.info(f"Minecraft reset for {task.id} finished in {_duration_ms(started)} ms.")
            return frame
        except BackendError as exc:
            logger.error(
                f"Minecraft reset for {task.id} failed during {self.phase} "
                f"after {_duration_ms(started)} ms: {exc}"
            )
            raise self._backend_error(f"reset failed: {exc}") from exc

    def step(self, commands: str) -> BackendFrame:
        if self.sock is None:
            raise BackendError("Minecraft socket is not connected")

        started = time.monotonic()
        logger.debug(
            f"Sending Minecraft step for {self.current_task_id}; "
            f"command payload is {len(commands.encode('utf-8'))} bytes."
        )
        try:
            self._phase("step_send")
            send_message(self.sock, f"<StepClient0>{commands}</StepClient0 >".encode("utf-8"))
            self._phase("step_recv_pov")
            pov = recv_message(self.sock)
            logger.debug(f"Received POV frame for {self.current_task_id}; payload is {len(pov)} bytes.")
            self._phase("step_recv_reward")
            reward_reply = recv_message(self.sock)
            reward, done, _sent = struct.unpack("!dbb", reward_reply)
            logger.debug(
                f"Received reward for {self.current_task_id}; reward={reward}, done={done}."
            )
            self._phase("step_recv_info")
            info = recv_message(self.sock).decode("utf-8")
            logger.debug(f"Received info for {self.current_task_id}; payload is {len(info)} bytes.")
            self._phase("step_server")
            send_message(self.sock, b"<StepServer></StepServer>")
            logger.debug(f"Minecraft step for {self.current_task_id} finished in {_duration_ms(started)} ms.")
            return BackendFrame(pov=pov, info=info, reward=reward, done=done == 1)
        except BackendError as exc:
            logger.error(
                f"Minecraft step for {self.current_task_id} failed during {self.phase} "
                f"after {_duration_ms(started)} ms: {exc}"
            )
            raise self._backend_error(f"step failed: {exc}") from exc

    def close(self) -> None:
        started = time.monotonic()
        self._phase("closing")
        logger.info(
            f"Closing Minecraft backend for {self.current_task_id}; port={self.port}; "
            f"process_state={self._process_snapshot()}; last_stdout={self._last_stdout_line()!r}."
        )
        if self.sock is not None:
            try:
                send_message(self.sock, b"<Disconnect/>")
            except Exception:
                pass
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.sock.close()
            self.sock = None

        self._terminate_process_group()
        self.process = None
        self.process_group_id = None

        if self.run_dir is not None:
            self.run_dir.cleanup()
            self.run_dir = None
        logger.info(f"Minecraft backend for {self.current_task_id} closed in {_duration_ms(started)} ms.")

    def _ensure_process(self, *, seed: int | None) -> None:
        if self.process is not None and self.process.is_running():
            return

        started = time.monotonic()
        port = self._choose_port()
        self.run_dir = tempfile.TemporaryDirectory(prefix="minerl-run-")
        launch_script = self.minecraft_dir / "launchClient.sh"
        cmd = [
            str(launch_script),
            "-port",
            str(port),
            "-env",
            "-runDir",
            self.run_dir.name,
            "-maxMem",
            self.max_mem,
        ]
        if seed is not None:
            cmd += ["-seed", str(seed)]

        logger.info(
            f"Launching Minecraft for {self.current_task_id} on port {port}; "
            f"run_dir={self.run_dir.name}, minecraft_dir={self.minecraft_dir}, "
            f"max_mem={self.max_mem}, socket_timeout={self.socket_timeout}."
        )
        self.process = psutil.Popen(
            cmd,
            cwd=str(self.minecraft_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.process_group_id = os.getpgid(self.process.pid)
        logger.info(
            f"Minecraft launch process started with pid={self.process.pid}, "
            f"pgid={self.process_group_id}; command={' '.join(cmd)!r}."
        )
        self._start_stdout_reader()
        self.port = self._wait_until_ready(port)
        logger.info(
            f"Minecraft is ready for {self.current_task_id} after {_duration_ms(started)} ms; "
            f"selected_port={self.port}."
        )

    def _terminate_process_group(self) -> None:
        if self.process is None:
            return

        logger.info(
            f"Terminating Minecraft process group for {self.current_task_id}; "
            f"before={self._process_snapshot()}."
        )
        pgid = self.process_group_id
        if pgid is not None:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except PermissionError:
                pass

        runtime_processes = self._runtime_processes()
        logger.debug(
            f"Terminating {len(runtime_processes)} Minecraft runtime processes for "
            f"{self.current_task_id}; pids={','.join(str(proc.pid) for proc in runtime_processes)}."
        )
        for proc in runtime_processes:
            try:
                proc.terminate()
            except psutil.Error:
                pass
        _, alive = psutil.wait_procs(runtime_processes, timeout=5)

        if pgid is not None:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                pass

        for proc in alive + self._runtime_processes():
            try:
                if proc.is_running():
                    proc.kill()
            except psutil.Error:
                pass

        psutil.wait_procs(self._runtime_processes(), timeout=2)
        logger.info(
            f"Minecraft process group termination finished for {self.current_task_id}; "
            f"after={self._process_snapshot()}."
        )

    def _runtime_processes(self) -> list[psutil.Process]:
        procs: dict[int, psutil.Process] = {}

        def add(proc: psutil.Process) -> None:
            try:
                procs[proc.pid] = proc
            except psutil.Error:
                pass

        try:
            if self.process is not None and self.process.is_running():
                for child in self.process.children(recursive=True):
                    add(child)
                add(self.process)
        except psutil.Error:
            pass

        run_dir = self.run_dir.name if self.run_dir is not None else None
        port_arg = f"--envPort={self.port}" if self.port is not None else None
        if run_dir is None and port_arg is None:
            return list(procs.values())

        for proc in psutil.process_iter(["cmdline"]):
            if proc.pid in procs:
                continue
            try:
                cmdline = proc.info.get("cmdline") or []
            except psutil.Error:
                continue
            command = " ".join(cmdline)
            if run_dir and run_dir in command:
                add(proc)
            elif port_arg and port_arg in command:
                add(proc)

        return list(procs.values())

    def _wait_until_ready(self, requested_port: int) -> int:
        assert self.process is not None
        deadline = time.monotonic() + LAUNCH_TIMEOUT
        last_log = 0.0
        while time.monotonic() < deadline:
            with self._stdout_condition:
                if self._stdout_ready:
                    return self._stdout_selected_port or requested_port
                remaining = max(0.0, min(1.0, deadline - time.monotonic()))
                self._stdout_condition.wait(timeout=remaining)
            if self.process.poll() is not None:
                raise self._backend_error(f"Minecraft exited before ready with code {self.process.returncode}")
            now = time.monotonic()
            if now - last_log >= 5.0:
                logger.info(
                    f"Waiting for Minecraft to become ready for {self.current_task_id}; "
                    f"elapsed={int((now - (deadline - LAUNCH_TIMEOUT)) * 1000)} ms, "
                    f"stdout_lines={self._stdout_counter}, last_stdout={self._last_stdout_line()!r}."
                )
                last_log = now
        raise self._backend_error("Minecraft did not become ready before launch timeout")

    def _connect(self) -> None:
        if self.sock is not None:
            return
        if self.port is None:
            raise BackendError("Minecraft port is unknown")
        started = time.monotonic()
        self._phase("connect")
        logger.debug(f"Connecting to Minecraft for {self.current_task_id} on port {self.port}.")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(self.socket_timeout)
        sock.connect(("localhost", self.port))
        send_message(sock, f"<MalmoEnv{MALMO_VERSION}/>".encode("utf-8"))
        self.sock = sock
        logger.debug(f"Connected to Minecraft for {self.current_task_id} in {_duration_ms(started)} ms.")

    def _quit_current_episode(self) -> None:
        assert self.sock is not None
        started = time.monotonic()
        self._phase("quit_old_episode")
        logger.debug(f"Asking Minecraft to quit any old episode for {self.current_task_id}.")
        send_message(self.sock, b"<Quit/>")
        recv_message(self.sock)
        logger.debug(
            f"Old episode quit request for {self.current_task_id} finished in {_duration_ms(started)} ms."
        )

    def _peek(self) -> BackendFrame:
        assert self.sock is not None
        started = time.monotonic()
        self._phase("peek")
        logger.debug(f"Peeking initial frame for {self.current_task_id}.")
        send_message(self.sock, b"<Peek/>")
        pov = recv_message(self.sock)
        info = recv_message(self.sock).decode("utf-8")
        done_reply = recv_message(self.sock)
        (done,) = struct.unpack("!b", done_reply)
        logger.debug(
            f"Initial frame for {self.current_task_id} arrived in {_duration_ms(started)} ms; "
            f"pov_bytes={len(pov)}, info_bytes={len(info)}, done={done}."
        )
        return BackendFrame(pov=pov, info=info, done=done == 1)

    def _start_stdout_reader(self) -> None:
        if self.process is None or self.process.stdout is None:
            return
        with self._stdout_condition:
            self.stdout_tail.clear()
            self._stdout_counter = 0
            self._stdout_ready = False
            self._stdout_selected_port = None

        encoding = locale.getpreferredencoding(False)

        def reader() -> None:
            assert self.process is not None and self.process.stdout is not None
            marker = "***** Start MalmoEnvServer on port "
            for raw in self.process.stdout:
                line = raw.decode(encoding, errors="replace").rstrip()
                with self._stdout_condition:
                    self.stdout_tail.append(line)
                    self._stdout_counter += 1
                    if marker in line:
                        self._stdout_selected_port = int(line.split(marker)[-1].strip())
                    if "CLIENT enter state: DORMANT" in line:
                        self._stdout_ready = True
                    self._stdout_condition.notify_all()
                logger.debug(f"Minecraft stdout: {line}")
            with self._stdout_condition:
                self._stdout_condition.notify_all()
            message = (
                f"Minecraft stdout reader ended for {self.current_task_id}; "
                f"phase={self.phase}; process_state={self._process_snapshot()}; "
                f"last_stdout={self._last_stdout_line()!r}."
            )
            if self.phase == "closing":
                logger.info(message)
            else:
                logger.warning(message)

        self._stdout_thread = threading.Thread(
            target=reader,
            name="minerl-minecraft-stdout",
            daemon=True,
        )
        self._stdout_thread.start()

    def _phase(self, phase: str) -> None:
        self.phase = phase

    def _last_stdout_line(self) -> str:
        with self._stdout_condition:
            return self.stdout_tail[-1] if self.stdout_tail else ""

    def _stdout_tail_text(self) -> str:
        with self._stdout_condition:
            return "\n".join(self.stdout_tail)

    def _process_snapshot(self) -> str:
        details: list[str] = []
        if self.process is None:
            details.append("launcher=None")
        else:
            try:
                details.append(f"launcher_pid={self.process.pid}")
                details.append(f"launcher_returncode={self.process.poll()}")
                details.append(f"launcher_running={self.process.is_running()}")
                details.append(f"launcher_status={self.process.status()}")
            except psutil.Error as exc:
                details.append(f"launcher_error={exc.__class__.__name__}:{exc}")

        try:
            runtime_processes = self._runtime_processes()
        except psutil.Error as exc:
            details.append(f"runtime_error={exc.__class__.__name__}:{exc}")
            return ";".join(details)

        runtime_details: list[str] = []
        for proc in runtime_processes:
            try:
                runtime_details.append(f"{proc.pid}:{proc.status()}")
            except psutil.Error as exc:
                runtime_details.append(f"{proc.pid}:{exc.__class__.__name__}")
        details.append(f"runtime_processes=[{','.join(runtime_details)}]")
        return ";".join(details)

    def _backend_error(self, message: str) -> BackendError:
        context = [
            message,
            f"phase={self.phase}",
            f"process_state={self._process_snapshot()}",
            "last_stdout:",
            self._stdout_tail_text(),
        ]
        return BackendError("\n".join(context))

    def _choose_port(self) -> int:
        port = self.base_port + ((os.getpid() * 17) % 3989)
        while _port_taken(port):
            port += 1
        return port


def _port_taken(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("localhost", port))
        return False
    except OSError:
        return True
    finally:
        sock.close()


def _duration_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
