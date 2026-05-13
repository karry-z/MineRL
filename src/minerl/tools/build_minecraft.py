from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from minerl.runtime.assets import find_minecraft_dir
from minerl.tools.patch_minecraft import patch_minecraft_tree


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the MineRL MCP-Reborn runtime jar")
    parser.add_argument(
        "--minecraft-dir",
        type=Path,
        default=None,
        help="MCP-Reborn directory. Defaults to MINERL_MINECRAFT_DIR or packaged assets.",
    )
    parser.add_argument("--no-patch", action="store_true", help="Skip source compatibility patches")
    args = parser.parse_args(argv)
    minecraft_dir = args.minecraft_dir or find_minecraft_dir()
    if not args.no_patch:
        patch_minecraft_tree(minecraft_dir)
    subprocess.check_call(["./gradlew", "clean", "build", "shadowJar"], cwd=minecraft_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
