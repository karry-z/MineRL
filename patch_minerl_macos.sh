#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python venv not found at: $PYTHON_BIN" >&2
  echo "Create/install the environment first, for example: uv sync" >&2
  exit 1
fi

MINERL_DIR="$("$PYTHON_BIN" - <<'PY'
from pathlib import Path
import minerl

print(Path(minerl.__file__).resolve().parent)
PY
)"

MCP_DIR="$MINERL_DIR/MCP-Reborn"

if [[ ! -d "$MCP_DIR" ]]; then
  echo "MineRL MCP-Reborn runtime not found at: $MCP_DIR" >&2
  exit 1
fi

PATCH_TARGET="$MCP_DIR" MINERL_TARGET="$MINERL_DIR" "$PYTHON_BIN" - <<'PY'
from pathlib import Path
import os
import re

mcp_dir = Path(os.environ["PATCH_TARGET"])
minerl_dir = Path(os.environ["MINERL_TARGET"])


def replace_method(text: str, signature: str, replacement: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"Could not find method signature: {signature}")

    brace = text.find("{", start)
    if brace < 0:
        raise RuntimeError(f"Could not find method body: {signature}")

    depth = 0
    end = None
    for index in range(brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break

    if end is None:
        raise RuntimeError(f"Could not find end of method body: {signature}")

    return text[:start] + replacement + text[end:]


def update_file(path: Path, updater) -> None:
    old = path.read_text()
    new = updater(old)
    try:
        display_path = path.relative_to(minerl_dir)
    except ValueError:
        display_path = path
    if old != new:
        path.write_text(new)
        print(f"patched {display_path}")
    else:
        print(f"already patched {display_path}")


launch_client = mcp_dir / "launchClient.sh"
build_gradle = mcp_dir / "build.gradle"
main_window = mcp_dir / "src/main/java/net/minecraft/client/MainWindow.java"
sound_engine = mcp_dir / "src/main/java/net/minecraft/client/audio/SoundEngine.java"
human_play_interface = minerl_dir / "human_play_interface/human_play_interface.py"

for path in (launch_client, build_gradle, main_window, sound_engine, human_play_interface):
    if not path.exists():
        raise RuntimeError(f"Required file does not exist: {path}")


def patch_launch_client(text: str) -> str:
    patched = re.sub(
        r"java -Xmx\$maxMem(?: -XstartOnFirstThread)? -jar \$fatjar --envPort=\$port",
        "java -Xmx$maxMem -XstartOnFirstThread -jar $fatjar --envPort=$port",
        text,
    )
    if "java -Xmx$maxMem -XstartOnFirstThread -jar $fatjar --envPort=$port" not in patched:
        raise RuntimeError("Failed to patch launchClient.sh")
    return patched


def patch_build_gradle(text: str) -> str:
    return text.replace("3.2.1", "3.3.1")


def patch_main_window(text: str) -> str:
    signature = "public static void checkGlfwError(BiConsumer<Integer, String> glfwErrorConsumer)"
    text = replace_method(text, signature, signature + " {\n   }")

    if "GLFW.glfwSetWindowIcon(this.handle, buffer);" in text:
        text = re.sub(
            r"^(\s*)GLFW\.glfwSetWindowIcon\(this\.handle, buffer\);",
            "\\1// Disabled for macOS Apple Silicon compatibility.\n"
            "\\1// GLFW.glfwSetWindowIcon(this.handle, buffer);",
            text,
            flags=re.MULTILINE,
        )

    return text


def patch_sound_engine(text: str) -> str:
    signature = "private synchronized void load()"
    replacement = """private synchronized void load() {
      if (!this.loaded) {
         this.soundsToPreload.clear();
         LOGGER.info(LOG_MARKER, "Sound engine disabled for MineRL Apple Silicon compatibility");

      }
   }"""
    return replace_method(text, signature, replacement)


def patch_human_play_interface(text: str) -> str:
    early_state = (
        "        self.pressed_keys = defaultdict(lambda: False)\n"
        "        self.last_pov = None\n"
        "        self.last_mouse_delta = [0, 0]\n"
    )
    if early_state in text:
        return text

    late_state = (
        "\n"
        "        self.last_pov = None\n"
        "        self.last_mouse_delta = [0, 0]\n"
    )
    if late_state not in text:
        raise RuntimeError("Could not find late HumanPlayInterface mouse state initialization")

    text = text.replace(late_state, "\n", 1)
    pressed_keys = "        self.pressed_keys = defaultdict(lambda: False)\n"
    if pressed_keys not in text:
        raise RuntimeError("Could not find HumanPlayInterface pressed_keys initialization")

    return text.replace(pressed_keys, early_state, 1)


update_file(launch_client, patch_launch_client)
update_file(build_gradle, patch_build_gradle)
update_file(main_window, patch_main_window)
update_file(sound_engine, patch_sound_engine)
update_file(human_play_interface, patch_human_play_interface)
PY

echo
echo "Checking patched files..."
grep -n "XstartOnFirstThread" "$MCP_DIR/launchClient.sh"
grep -n "3.3.1" "$MCP_DIR/build.gradle" | head -n 3
grep -nE "checkGlfwError|glfwSetWindowIcon" "$MCP_DIR/src/main/java/net/minecraft/client/MainWindow.java"
grep -n "Sound engine disabled" "$MCP_DIR/src/main/java/net/minecraft/client/audio/SoundEngine.java"
grep -n "last_mouse_delta" "$MINERL_DIR/human_play_interface/human_play_interface.py"

echo
echo "Rebuilding MineRL Minecraft runtime..."
(
  cd "$MCP_DIR"
  ./gradlew clean build shadowJar
)

echo
echo "Done. Run: uv run python main.py"
