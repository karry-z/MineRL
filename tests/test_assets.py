from __future__ import annotations

import os
from pathlib import Path

from minerl.runtime import assets


def test_packaged_minecraft_assets_are_available(monkeypatch) -> None:
    monkeypatch.delenv("MINERL_MINECRAFT_DIR", raising=False)

    minecraft_dir = assets.find_minecraft_dir()

    assert minecraft_dir == assets.package_root() / "assets" / "MCP-Reborn"
    assert (minecraft_dir / "launchClient.sh").is_file()
    assert os.access(minecraft_dir / "launchClient.sh", os.X_OK)
    assert (minecraft_dir / "build/libs/mcprec-6.13.jar").is_file()


def test_packaged_malmo_assets_are_available() -> None:
    malmo_dir = assets.package_root() / "assets" / "Malmo"

    assert (malmo_dir / "Schemas/Mission.xsd").is_file()
    assert (malmo_dir / "Schemas/MissionInit.xsd").is_file()


def test_minecraft_dir_env_override_wins(tmp_path: Path, monkeypatch) -> None:
    override = tmp_path / "MCP-Reborn"
    (override / "build/libs").mkdir(parents=True)
    launch = override / "launchClient.sh"
    launch.write_text("#!/bin/sh\n")
    launch.chmod(0o755)
    (override / "build/libs/mcprec-6.13.jar").write_bytes(b"jar")
    monkeypatch.setenv("MINERL_MINECRAFT_DIR", str(override))

    assert assets.find_minecraft_dir() == override


def test_minecraft_dir_error_reports_required_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MINERL_MINECRAFT_DIR", raising=False)
    monkeypatch.setattr(assets, "package_root", lambda: tmp_path)

    try:
        assets.find_minecraft_dir()
    except FileNotFoundError as exc:
        message = str(exc)
        assert "launchClient.sh" in message
        assert "build/libs/mcprec-6.13.jar" in message
    else:
        raise AssertionError("expected missing packaged assets to raise")
