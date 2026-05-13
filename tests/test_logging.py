from __future__ import annotations

import subprocess
import sys

import psutil

from minerl.runtime.minecraft import MinecraftBackend


def test_import_does_not_configure_root_logging() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import logging\n"
                "before = len(logging.getLogger().handlers)\n"
                "import minerl\n"
                "after = len(logging.getLogger().handlers)\n"
                "print(f'{before} {after}')\n"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "0 0"


def test_minecraft_stdout_reader_drains_and_keeps_tail() -> None:
    process = psutil.Popen(
        [
            sys.executable,
            "-c",
            "import sys\nfor i in range(260): print(f'line-{i}', flush=True)",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    backend = MinecraftBackend(minecraft_dir="src/minerl/assets/MCP-Reborn")
    backend.process = process

    backend._start_stdout_reader()
    process.wait(timeout=5)
    assert backend._stdout_thread is not None
    backend._stdout_thread.join(timeout=5)

    assert len(backend.stdout_tail) == 200
    assert backend.stdout_tail[-1] == "line-259"
    assert backend.stdout_tail[0] == "line-60"
