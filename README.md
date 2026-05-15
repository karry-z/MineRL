# MineRL on Apple Silicon macOS

Quick start for running the local MineRL environment on Apple Silicon macOS.

## Requirements

- Apple Silicon Mac.
- Homebrew.
- Java 8.
- `uv` for Python environment management.

Install the required tools:

```bash
brew install --cask temurin@8
brew install uv
```

Use Java 8 in this shell:

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 1.8)
export PATH="$JAVA_HOME/bin:$PATH"
java -version
```

Expected Java version shape:

```text
java version "1.8.0_..."
```

## Quick Start

Clone this repository:

```bash
git clone git@github.com:karry-z/MineRL.git
cd MineRL
```

Create the Python environment:

```bash
uv sync
```

Build the Minecraft runtime jar:

```bash
uv run python -m minerl.tools.build_minecraft
```

Run the human-play demo:

```bash
uv run python main.py
```

The first build can take several minutes because Gradle downloads and builds the
Minecraft runtime. The first `env.reset()` can also take tens of seconds because
it starts Minecraft.

## Controls

```text
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
```

## What Gets Built

The command below creates the runtime jar used by `main.py`:

```text
src/minerl/assets/MCP-Reborn/build/libs/mcprec-6.13.jar
```

That jar is a generated build artifact and is not committed to git. A fresh
clone must build it once before running the environment.

## Troubleshooting

### `Could not locate a usable MCP-Reborn runtime`

The runtime jar has not been built yet. Run:

```bash
uv run python -m minerl.tools.build_minecraft
```

### `ModuleNotFoundError`

The Python environment is missing dependencies. Recreate it:

```bash
rm -rf .venv
uv sync
```

### Java is not version 8

Select Java 8 again:

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 1.8)
export PATH="$JAVA_HOME/bin:$PATH"
java -version
```

## Logs

Runtime logs are written under:

```text
~/.cache/minerl/logs
```

## References

- MineRL tutorial docs: https://minerl.readthedocs.io/en/latest/tutorials/index.html
- MineRL macOS issue comment: https://github.com/minerllabs/minerl/issues/659#issuecomment-1306635414
- Homebrew `temurin@8` cask: https://formulae.brew.sh/cask/temurin%408
