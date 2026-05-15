from __future__ import annotations

import os
from pathlib import Path

LAUNCH_SCRIPT = "launchClient.sh"
LAUNCH_JAR = Path("build/libs/mcprec-6.13.jar")
SOURCE_FILES = (
    Path(LAUNCH_SCRIPT),
    Path("gradlew"),
    Path("build.gradle"),
    Path("settings.gradle"),
)


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_minecraft_dir() -> Path:
    """Locate a built MCP-Reborn runtime for local development or installed package use."""
    candidates = _minecraft_candidates()

    for _, candidate in candidates:
        if _is_minecraft_dir(candidate):
            return candidate

    searched = "; ".join(
        _describe_candidate(label, path, required=(Path(LAUNCH_SCRIPT), LAUNCH_JAR))
        for label, path in candidates
    )
    raise FileNotFoundError(
        "Could not locate a usable MCP-Reborn runtime. Set MINERL_MINECRAFT_DIR or build "
        "the packaged runtime with `python -m minerl.tools.build_minecraft`. "
        f"Required files: {LAUNCH_SCRIPT}, {LAUNCH_JAR}. Checked: {searched}"
    )


def find_minecraft_source_dir() -> Path:
    """Locate MCP-Reborn sources, even before the runtime jar has been built."""
    candidates = _minecraft_candidates()

    for _, candidate in candidates:
        if _is_minecraft_source_dir(candidate):
            return candidate

    searched = "; ".join(
        _describe_candidate(label, path, required=SOURCE_FILES) for label, path in candidates
    )
    required = ", ".join(str(path) for path in SOURCE_FILES)
    raise FileNotFoundError(
        "Could not locate MCP-Reborn sources. Set MINERL_MINECRAFT_DIR or install "
        f"the packaged assets. Required files: {required}. Checked: {searched}"
    )


def _minecraft_candidates() -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    env_dir = os.environ.get("MINERL_MINECRAFT_DIR")
    if env_dir:
        candidates.append(("MINERL_MINECRAFT_DIR", Path(env_dir)))

    candidates.append(("packaged assets", package_root() / "assets" / "MCP-Reborn"))
    return candidates


def _is_minecraft_dir(path: Path) -> bool:
    return (path / LAUNCH_SCRIPT).is_file() and (path / LAUNCH_JAR).is_file()


def _is_minecraft_source_dir(path: Path) -> bool:
    return all((path / required).is_file() for required in SOURCE_FILES)


def _describe_candidate(label: str, path: Path, *, required: tuple[Path, ...]) -> str:
    missing = [str(name) for name in required if not (path / name).is_file()]
    if not missing:
        return f"{label}={path} (ok)"
    return f"{label}={path} (missing {', '.join(missing)})"
