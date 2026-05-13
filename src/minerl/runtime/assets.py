from __future__ import annotations

import os
from pathlib import Path

LAUNCH_SCRIPT = "launchClient.sh"
LAUNCH_JAR = Path("build/libs/mcprec-6.13.jar")


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_minecraft_dir() -> Path:
    """Locate MCP-Reborn for local development or installed package use."""
    candidates: list[tuple[str, Path]] = []
    env_dir = os.environ.get("MINERL_MINECRAFT_DIR")
    if env_dir:
        candidates.append(("MINERL_MINECRAFT_DIR", Path(env_dir)))

    candidates.append(("packaged assets", package_root() / "assets" / "MCP-Reborn"))

    for _, candidate in candidates:
        if _is_minecraft_dir(candidate):
            return candidate

    searched = "; ".join(_describe_candidate(label, path) for label, path in candidates)
    raise FileNotFoundError(
        "Could not locate a usable MCP-Reborn runtime. Set MINERL_MINECRAFT_DIR or install "
        f"the packaged assets. Required files: {LAUNCH_SCRIPT}, {LAUNCH_JAR}. Checked: {searched}"
    )


def _is_minecraft_dir(path: Path) -> bool:
    return (path / LAUNCH_SCRIPT).is_file() and (path / LAUNCH_JAR).is_file()


def _describe_candidate(label: str, path: Path) -> str:
    missing = []
    if not (path / LAUNCH_SCRIPT).is_file():
        missing.append(LAUNCH_SCRIPT)
    if not (path / LAUNCH_JAR).is_file():
        missing.append(str(LAUNCH_JAR))
    if not missing:
        return f"{label}={path} (ok)"
    return f"{label}={path} (missing {', '.join(missing)})"
