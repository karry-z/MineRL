from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
import logging
import time
from collections import defaultdict
from typing import Any, Callable, TypeVar

import gymnasium as gym
import numpy as np
from gymnasium import spaces

logger = logging.getLogger(__name__)

MINERL_ACTION_TO_KEYBOARD = {
    "ESC": "ESCAPE",
    "attack": "MOUSE_LEFT",
    "back": "S",
    "drop": "Q",
    "forward": "W",
    "hotbar.1": "_1",
    "hotbar.2": "_2",
    "hotbar.3": "_3",
    "hotbar.4": "_4",
    "hotbar.5": "_5",
    "hotbar.6": "_6",
    "hotbar.7": "_7",
    "hotbar.8": "_8",
    "hotbar.9": "_9",
    "inventory": "E",
    "jump": "SPACE",
    "left": "A",
    "pickItem": "MOUSE_MIDDLE",
    "right": "D",
    "sneak": "LSHIFT",
    "sprint": "LCTRL",
    "swapHands": "F",
    "use": "MOUSE_RIGHT",
}

MOUSE_MULTIPLIER = 0.1
FRAME_TIME = 1 / 20
PROGRESS_SHOW_AFTER = 0.35
PROGRESS_UPDATE_INTERVAL = 0.25
ESC_CONFIRM_WINDOW = 2.0

T = TypeVar("T")


class HumanPlayInterface(gym.Wrapper):
    """Pyglet-based human control wrapper for Gymnasium MineRL envs."""

    def __init__(self, env: gym.Env):
        super().__init__(env)
        self._validate_env()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="minerl-human")
        pyglet, key = _load_pyglet()
        self._pyglet = pyglet
        self._key = key
        self._keymap = _resolve_keymap(pyglet, key)
        self.pressed_keys = defaultdict(lambda: False)
        self.last_mouse_delta = [0.0, 0.0]
        self.last_pov: np.ndarray | None = None
        self.step_count = 0
        self.window_close_requested = False
        self.last_action_summary = "none"
        self._esc_armed_until = 0.0
        self._esc_exit_requested = False
        self.start_time = time.time()

        pov_shape = self.observation_space["pov"].shape
        self.window = pyglet.window.Window(
            width=pov_shape[1],
            height=pov_shape[0],
            vsync=False,
            resizable=False,
        )
        self.window.on_mouse_motion = self._on_mouse_motion
        self.window.on_mouse_drag = self._on_mouse_drag
        self.window.on_key_press = self._on_key_press
        self.window.on_key_release = self._on_key_release
        self.window.on_mouse_press = self._on_mouse_press
        self.window.on_mouse_release = self._on_mouse_release
        self.window.on_activate = self._on_window_activate
        self.window.on_deactivate = self._on_window_deactivate
        self.window.push_handlers(on_close=self._on_window_close)
        self.window.dispatch_events()
        self.window.switch_to()
        self.window.flip()
        self._show_message("Waiting for reset.")

    def reset(self, **kwargs):
        self.window.clear()
        obs, info = self._run_backend_call(
            lambda: self.env.reset(**kwargs),
            "Resetting environment",
            show_after=0.0,
        )
        self._update_image(obs["pov"])
        return obs, info

    def step(self, action: dict[str, Any] | None = None, override_if_human_input: bool = False):
        elapsed = time.time() - self.start_time
        if elapsed < FRAME_TIME:
            time.sleep(FRAME_TIME - elapsed)
        self.start_time = time.time()

        if action is None or override_if_human_input:
            self.window.dispatch_events()
            human_action = self._get_human_action()
            if action is None or _has_input(human_action):
                action = human_action
        self.last_action_summary = _summarize_action(action)

        obs, reward, terminated, truncated, info = self._run_backend_call(
            lambda: self.env.step(action),
            "Waiting for Minecraft step",
            show_after=PROGRESS_SHOW_AFTER,
        )
        self.step_count += 1
        self._update_image(obs["pov"])
        if terminated or truncated:
            logger.info(
                "HumanPlayInterface observed episode end; "
                f"steps={self.step_count}, terminated={terminated}, truncated={truncated}, "
                f"last_action={self.last_action_summary}, info_keys={sorted(info)}."
            )
            self._show_message("Episode done.")
        info = dict(info)
        info["taken_action"] = action
        return obs, reward, terminated, truncated, info

    def close(self) -> None:
        logger.info(
            "Closing HumanPlayInterface; "
            f"steps={self.step_count}, window_close_requested={self.window_close_requested}, "
            f"last_action={self.last_action_summary}."
        )
        try:
            self.window.close()
        finally:
            try:
                self.env.close()
            finally:
                self._executor.shutdown(wait=False, cancel_futures=True)

    def _validate_env(self) -> None:
        if not isinstance(self.action_space, spaces.Dict):
            raise RuntimeError("HumanPlayInterface requires a Dict action space")
        if not isinstance(self.observation_space, spaces.Dict) or "pov" not in (
            self.observation_space.spaces
        ):
            raise RuntimeError("HumanPlayInterface requires a pov observation")
        for action_name, action_space in self.action_space.spaces.items():
            if action_name == "camera":
                continue
            if action_name not in MINERL_ACTION_TO_KEYBOARD:
                raise RuntimeError(f"Unsupported human action: {action_name}")
            if not isinstance(action_space, spaces.Discrete) or action_space.n != 2:
                raise RuntimeError(f"Human action {action_name} must be Discrete(2)")

    def _get_human_action(self) -> dict[str, Any]:
        action = self.env.unwrapped.no_op_action()
        for name, symbol in self._keymap.items():
            if name in action:
                if name == "ESC":
                    action[name] = self._consume_esc_action()
                    continue
                action[name] = int(self.pressed_keys[symbol])
        action["camera"] = np.asarray(self.last_mouse_delta, dtype=np.float32)
        self.last_mouse_delta = [0.0, 0.0]
        return action

    def _run_backend_call(
        self,
        call: Callable[[], T],
        label: str,
        *,
        show_after: float,
    ) -> T:
        future = self._executor.submit(call)
        started = time.monotonic()
        last_update = 0.0
        last_log_update = 0.0

        while True:
            try:
                return future.result(timeout=0.05)
            except TimeoutError:
                self.window.dispatch_events()
                now = time.monotonic()
                elapsed = now - started
                if elapsed >= show_after and now - last_update >= PROGRESS_UPDATE_INTERVAL:
                    self._show_message(f"{label}... {elapsed:.1f}s", clear=True)
                    last_update = now
                if elapsed >= show_after and now - last_log_update >= 2.0:
                    logger.info(f"{label} has been waiting for {int(elapsed * 1000)} ms.")
                    last_log_update = now

    def _update_image(self, arr: np.ndarray) -> None:
        self.last_pov = arr
        self.window.switch_to()
        image = self._pyglet.image.ImageData(
            arr.shape[1],
            arr.shape[0],
            "RGB",
            arr.tobytes(),
            pitch=arr.shape[1] * -3,
        )
        image.get_texture().blit(0, 0)
        self._draw_esc_prompt_if_armed()
        self.window.flip()

    def _show_message(self, text: str, *, clear: bool = False) -> None:
        self.window.switch_to()
        if clear:
            self.window.clear()
        label = self._pyglet.text.Label(
            text,
            font_size=32,
            x=self.window.width // 2,
            y=self.window.height // 2,
            anchor_x="center",
            anchor_y="center",
        )
        label.draw()
        self.window.flip()

    def _on_key_press(self, symbol, modifiers) -> None:
        was_pressed = self.pressed_keys[symbol]
        self.pressed_keys[symbol] = True
        if symbol == self._keymap["ESC"] and not was_pressed:
            self._handle_esc_press()

    def _on_key_release(self, symbol, modifiers) -> None:
        self.pressed_keys[symbol] = False

    def _on_mouse_press(self, x, y, button, modifiers) -> None:
        self.pressed_keys[button] = True

    def _on_mouse_release(self, x, y, button, modifiers) -> None:
        self.pressed_keys[button] = False

    def _on_window_activate(self) -> None:
        self.window.set_mouse_visible(False)
        self.window.set_exclusive_mouse(True)

    def _on_window_deactivate(self) -> None:
        logger.debug("HumanPlayInterface window deactivated.")
        self.window.set_mouse_visible(True)
        self.window.set_exclusive_mouse(False)

    def _on_window_close(self) -> None:
        self.window_close_requested = True
        logger.warning(
            "Pyglet window close event received; "
            f"steps={self.step_count}, last_action={self.last_action_summary}."
        )

    def _on_mouse_motion(self, x, y, dx, dy) -> None:
        self.last_mouse_delta[0] -= dy * MOUSE_MULTIPLIER
        self.last_mouse_delta[1] += dx * MOUSE_MULTIPLIER

    def _on_mouse_drag(self, x, y, dx, dy, button, modifier) -> None:
        self._on_mouse_motion(x, y, dx, dy)

    def _handle_esc_press(self) -> None:
        now = time.monotonic()
        if now <= self._esc_armed_until:
            self._esc_exit_requested = True
            self._esc_armed_until = 0.0
            logger.info(
                "ESC confirmation accepted; ending episode on next environment step. "
                f"steps={self.step_count}."
            )
            self._show_message("Exiting episode...", clear=True)
            return

        self._esc_exit_requested = False
        self._esc_armed_until = now + ESC_CONFIRM_WINDOW
        logger.info(
            "ESC pressed once; waiting for confirmation before ending episode. "
            f"confirm_window_seconds={ESC_CONFIRM_WINDOW:g}, steps={self.step_count}."
        )
        self._show_message(_esc_prompt_text(), clear=True)

    def _consume_esc_action(self) -> int:
        if self._esc_exit_requested:
            self._esc_exit_requested = False
            self._esc_armed_until = 0.0
            return 1
        if self._esc_armed_until and time.monotonic() > self._esc_armed_until:
            self._esc_armed_until = 0.0
        return 0

    def _draw_esc_prompt_if_armed(self) -> None:
        if not self._esc_armed_until or time.monotonic() > self._esc_armed_until:
            return
        label = self._pyglet.text.Label(
            _esc_prompt_text(),
            font_size=24,
            x=self.window.width // 2,
            y=self.window.height // 2,
            anchor_x="center",
            anchor_y="center",
        )
        label.draw()


def _load_pyglet():
    try:
        import pyglet
        import pyglet.window.key as key
    except ImportError as exc:
        raise RuntimeError("Install minerl-modern[human] to use HumanPlayInterface") from exc
    return pyglet, key


def _resolve_keymap(pyglet, key) -> dict[str, int]:
    mouse = pyglet.window.mouse
    lookup = {
        "MOUSE_LEFT": mouse.LEFT,
        "MOUSE_MIDDLE": mouse.MIDDLE,
        "MOUSE_RIGHT": mouse.RIGHT,
    }
    for name in set(MINERL_ACTION_TO_KEYBOARD.values()) - set(lookup):
        lookup[name] = getattr(key, name)
    return {action: lookup[symbol] for action, symbol in MINERL_ACTION_TO_KEYBOARD.items()}


def _has_input(action: dict[str, Any]) -> bool:
    for name, value in action.items():
        if name == "camera":
            if np.any(np.asarray(value) != 0):
                return True
        elif value:
            return True
    return False


def _summarize_action(action: dict[str, Any] | None) -> str:
    if not action:
        return "none"
    active: list[str] = []
    for name, value in action.items():
        if name == "camera":
            array = np.asarray(value)
            if np.any(array != 0):
                active.append(f"camera={array.tolist()}")
        elif value:
            active.append(str(name))
    return ",".join(active) if active else "noop"


def _esc_prompt_text() -> str:
    return f"Esc will end the episode. Press Esc again within {ESC_CONFIRM_WINDOW:g}s to confirm."
