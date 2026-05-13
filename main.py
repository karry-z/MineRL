from datetime import datetime
import atexit
import os
import logging
from pathlib import Path
import signal
import sys
import time
from typing import Any

import gymnasium as gym
import pyglet
from minerl.human_play_interface import HumanPlayInterface

os.environ["PYTHONWARNINGS"] = "ignore::RuntimeWarning:runpy"
pyglet.options["dpi_scaling"] = "stretch"

DEFAULT_LOG_DIR = Path.home() / ".cache" / "minerl" / "logs"


CONTROLS = """
Controls:
  W/A/S/D      move
  Space        jump
  Left Ctrl    sprint
  Left Shift   sneak
  Mouse        look
  Left click   attack
  Right click  use
  E            inventory
  Q            drop
  1-9          hotbar
  Esc          end episode
"""


def main():
    log_file = configure_app_logging()
    logger = logging.getLogger(__name__)
    _install_shutdown_diagnostics(logger)
    logger.info(f"Starting MineRL human play. Logs are written to {log_file}.")
    env = gym.make("MineRLBasaltFindCave-v0")
    env = HumanPlayInterface(env)

    print(CONTROLS)
    obs, info = env.reset()
    terminated = False
    truncated = False
    exit_reason = "main loop left without a recorded reason"
    step_count = 0
    last_reward = 0.0
    last_info: dict[str, Any] = dict(info)
    started = time.monotonic()

    try:
        while not (terminated or truncated):
            obs, reward, terminated, truncated, info = env.step()
            step_count += 1
            last_reward = float(reward)
            last_info = dict(info)
            if terminated:
                exit_reason = f"episode terminated; info={_summarize_info(last_info)}"
            elif truncated:
                exit_reason = f"episode truncated; info={_summarize_info(last_info)}"
        logger.info(
            "MineRL main loop finished normally; "
            f"reason={exit_reason}; steps={step_count}; last_reward={last_reward}."
        )
    except KeyboardInterrupt:
        exit_reason = "KeyboardInterrupt or SIGINT"
        logger.exception(
            "MineRL main loop interrupted; "
            f"steps={step_count}; last_reward={last_reward}; last_info={_summarize_info(last_info)}."
        )
        raise
    except SystemExit as exc:
        exit_reason = f"SystemExit code={exc.code!r}"
        logger.exception(
            "MineRL main loop received SystemExit; "
            f"steps={step_count}; last_reward={last_reward}; last_info={_summarize_info(last_info)}."
        )
        raise
    except BaseException:
        exit_reason = "unhandled exception"
        logger.exception(
            "MineRL main loop failed; "
            f"steps={step_count}; last_reward={last_reward}; last_info={_summarize_info(last_info)}."
        )
        raise
    finally:
        logger.info(
            "MineRL main loop is closing env; "
            f"reason={exit_reason}; steps={step_count}; "
            f"runtime_ms={int((time.monotonic() - started) * 1000)}."
        )
        try:
            env.close()
        finally:
            logger.info("MineRL main cleanup finished.")
            _flush_log_handlers()


def configure_app_logging() -> Path:
    level_name = os.environ.get("MINERL_LOG_LEVEL", "INFO").upper()
    console_level = getattr(logging, level_name, logging.INFO)
    log_file = _log_file_from_environment()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[console_handler, file_handler],
        force=True,
    )
    return log_file


def _log_file_from_environment() -> Path:
    if path := os.environ.get("MINERL_LOG_FILE"):
        return Path(path).expanduser()
    directory = Path(os.environ.get("MINERL_LOG_DIR", DEFAULT_LOG_DIR)).expanduser()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return directory / f"minerl-{stamp}-{os.getpid()}.log"


def _install_shutdown_diagnostics(logger: logging.Logger) -> None:
    def log_process_exit() -> None:
        logger.info("Python process exit hook ran.")
        _flush_log_handlers()

    atexit.register(log_process_exit)

    for signal_name in ("SIGINT", "SIGTERM", "SIGHUP"):
        signum = getattr(signal, signal_name, None)
        if signum is None:
            continue

        def handle_signal(received: int, frame: object | None, *, name: str = signal_name) -> None:
            logger.warning(f"Received {name}; raising SystemExit so cleanup is logged.")
            _flush_log_handlers()
            if received == signal.SIGINT:
                raise KeyboardInterrupt(name)
            raise SystemExit(128 + received)

        signal.signal(signum, handle_signal)


def _summarize_info(info: dict[str, Any]) -> str:
    if not info:
        return "{}"
    fields: dict[str, Any] = {}
    for key in ("terminated_by", "error", "backend_done"):
        if key in info:
            fields[key] = info[key]
    if "taken_action" in info:
        fields["taken_action"] = _summarize_action(info["taken_action"])
    if not fields:
        fields["keys"] = sorted(info)
    return repr(fields)


def _summarize_action(action: Any) -> str:
    if not isinstance(action, dict):
        return repr(action)
    active: list[str] = []
    for key, value in action.items():
        if key == "camera":
            if _truthy_array_like(value):
                active.append(f"camera={_compact_value(value)}")
        elif _truthy_array_like(value):
            active.append(str(key))
    return ",".join(active) if active else "noop"


def _truthy_array_like(value: Any) -> bool:
    try:
        return bool(value.any())
    except AttributeError:
        pass
    try:
        return bool(value)
    except ValueError:
        return True


def _compact_value(value: Any) -> Any:
    try:
        return value.tolist()
    except AttributeError:
        return value


def _flush_log_handlers() -> None:
    for handler in logging.getLogger().handlers:
        handler.flush()


if __name__ == "__main__":
    main()
