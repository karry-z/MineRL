from __future__ import annotations

import socket

import gymnasium as gym
import minerl  # noqa: F401
from minerl.protocol.wire import ProtocolError, recv_message, send_message
from minerl.runtime.backend import BackendError
from minerl.tasks.catalog import get_task


def test_wire_protocol_roundtrip() -> None:
    a, b = socket.socketpair()
    try:
        send_message(a, b"hello")
        assert recv_message(b) == b"hello"
    finally:
        a.close()
        b.close()


def test_wire_protocol_timeout_is_backend_error(caplog) -> None:
    caplog.set_level("WARNING", logger="minerl.protocol.wire")
    a, b = socket.socketpair()
    try:
        a.settimeout(0.01)
        try:
            recv_message(a)
        except ProtocolError as exc:
            assert "timed out" in str(exc)
        else:
            raise AssertionError("expected recv_message to convert socket.timeout")
    finally:
        a.close()
        b.close()
    assert "Timed out while reading from Minecraft" in "\n".join(record.getMessage() for record in caplog.records)


class FailingBackend:
    def reset(self, task, *, seed, options):
        raise BackendError("boom")

    def step(self, commands):
        raise AssertionError("step should not reach backend after failed reset")

    def close(self):
        pass


def test_reset_failure_is_reported_and_next_step_truncates() -> None:
    env = gym.make("MineRLTreechop-v0", backend=FailingBackend())
    try:
        obs, info = env.reset()
        assert "error" in info
        _, reward, terminated, truncated, step_info = env.step(env.unwrapped.no_op_action())
        assert reward == 0.0
        assert terminated is False
        assert truncated is True
        assert "error" in step_info
    finally:
        env.close()


def test_unknown_task_raises_clear_error() -> None:
    try:
        get_task("MineRLDoesNotExist-v0")
    except KeyError as exc:
        assert "Unknown MineRL task" in str(exc)
    else:
        raise AssertionError("expected get_task to reject unknown task")
