from __future__ import annotations

import argparse
import re
from pathlib import Path

from minerl.runtime.assets import find_minecraft_dir


def patch_minecraft_tree(minecraft_dir: Path) -> list[Path]:
    """Apply source-level compatibility patches to MCP-Reborn.

    The function is intentionally idempotent and only touches the files needed
    for the retained Java/Minecraft runtime.
    """
    changed: list[Path] = []
    targets = {
        "launch": minecraft_dir / "launchClient.sh",
        "gradle": minecraft_dir / "build.gradle",
        "window": minecraft_dir / "src/main/java/net/minecraft/client/MainWindow.java",
        "sound": minecraft_dir / "src/main/java/net/minecraft/client/audio/SoundEngine.java",
    }
    for path in targets.values():
        if not path.exists():
            raise FileNotFoundError(path)

    if _update_file(targets["launch"], _patch_launch_client):
        changed.append(targets["launch"])
    if _update_file(targets["gradle"], _patch_build_gradle):
        changed.append(targets["gradle"])
    if _update_file(targets["window"], _patch_main_window):
        changed.append(targets["window"])
    if _update_file(targets["sound"], _patch_sound_engine):
        changed.append(targets["sound"])
    return changed


def _update_file(path: Path, updater) -> bool:
    old = path.read_text()
    new = updater(old)
    if old == new:
        return False
    path.write_text(new)
    return True


def _patch_launch_client(text: str) -> str:
    return re.sub(
        r"java -Xmx\$maxMem(?: -XstartOnFirstThread)? -jar \$fatjar --envPort=\$port",
        "java -Xmx$maxMem -XstartOnFirstThread -jar $fatjar --envPort=$port",
        text,
    )


def _patch_build_gradle(text: str) -> str:
    text = text.replace("jcenter()", 'maven { url = "https://maven.minecraftforge.net/" }')
    return text.replace("3.2.1", "3.3.1")


def _patch_main_window(text: str) -> str:
    text = _replace_method(
        text,
        "public static void checkGlfwError(BiConsumer<Integer, String> glfwErrorConsumer)",
        "public static void checkGlfwError(BiConsumer<Integer, String> glfwErrorConsumer) {\n   }",
    )
    return re.sub(
        r"^(\s*)GLFW\.glfwSetWindowIcon\(this\.handle, buffer\);",
        r"\1// GLFW.glfwSetWindowIcon(this.handle, buffer);",
        text,
        flags=re.MULTILINE,
    )


def _patch_sound_engine(text: str) -> str:
    replacement = """private synchronized void load() {
      if (!this.loaded) {
         this.soundsToPreload.clear();
         LOGGER.info(LOG_MARKER, "Sound engine disabled for MineRL compatibility");
      }
   }"""
    return _replace_method(text, "private synchronized void load()", replacement)


def _replace_method(text: str, signature: str, replacement: str) -> str:
    start = text.find(signature)
    if start == -1:
        if replacement in text:
            return text
        raise ValueError(f"Could not find method signature: {signature}")

    brace_start = text.find("{", start)
    if brace_start == -1:
        raise ValueError(f"Could not find opening brace for: {signature}")

    depth = 0
    for index in range(brace_start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement + text[index + 1 :]
    raise ValueError(f"Could not find closing brace for: {signature}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Patch the retained MCP-Reborn runtime")
    parser.add_argument("--minecraft-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    minecraft_dir = args.minecraft_dir or find_minecraft_dir()
    changed = patch_minecraft_tree(minecraft_dir)
    for path in changed:
        print(f"patched {path}")
    if not changed:
        print("already patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
