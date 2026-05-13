# MineRL on Apple Silicon macOS

This is a migration note for setting up MineRL on Apple Silicon macOS. Run the commands from the project directory you want to use.

## 1. Install Java 8

```bash
brew install --cask temurin@8
java -version
```

MineRL needs Java 8 for the Minecraft/Malmo runtime.

The official MineRL tutorial still points to the old `adoptopenjdk8` cask. That can fail with:

```text
Error: Cask 'adoptopenjdk8' definition is invalid: undefined method 'appcast' for Cask 'adoptopenjdk8'
```

Use `temurin@8` instead. If `java -version` prints a version like `1.8.0_492`, that is Java 8.

## 2. Install MineRL

```bash
uv venv -p 3.10
source .venv/bin/activate
uv init
uv add git+https://github.com/minerllabs/minerl
```

This creates a Python 3.10 virtual environment and installs MineRL from the official GitHub repository.

Python 3.10 is used because MineRL's dependency stack is old. Newer Python versions can introduce dependency and build issues.

## 3. Patch and rebuild the MineRL Minecraft runtime

Recommended command for a fresh environment:

```bash
./patch_minerl_macos.sh
```

The script is idempotent: it can be run again after recreating `.venv` or reinstalling MineRL. It patches the MineRL files under `.venv/lib/python3.10/site-packages/minerl/MCP-Reborn` and rebuilds `build/libs/mcprec-6.13.jar`.

It applies these fixes:

- add `-XstartOnFirstThread` to the Minecraft Java launcher
- upgrade LWJGL dependency strings from `3.2.1` to `3.3.1`
- disable `MainWindow.checkGlfwError`
- disable `GLFW.glfwSetWindowIcon`
- disable Minecraft `SoundEngine` to avoid Apple Silicon `liblwjgl_stb.dylib` crashes in the audio thread
- initialize `HumanPlayInterface` mouse state before pyglet dispatches window events

The Python entrypoint also needs to set these before importing `HumanPlayInterface`; this repository's `main.py` already does it:

```python
import os

os.environ["PYTHONWARNINGS"] = "ignore::RuntimeWarning:runpy"

import pyglet

pyglet.options["dpi_scaling"] = "stretch"
```

### 3.1 Add `-XstartOnFirstThread`

Command:

```bash
perl -0pi -e 's/java -Xmx\$maxMem -jar/java -Xmx\$maxMem -XstartOnFirstThread -jar/' \
  .venv/lib/python3.10/site-packages/minerl/MCP-Reborn/launchClient.sh
```

Manual edit:

```text
.venv/lib/python3.10/site-packages/minerl/MCP-Reborn/launchClient.sh
```

Change the Java launch line from:

```bash
java -Xmx$maxMem -jar $fatjar --envPort=$port
```

to:

```bash
java -Xmx$maxMem -XstartOnFirstThread -jar $fatjar --envPort=$port
```

This fixes:

```text
java.lang.IllegalStateException: GLFW windows may only be created on the main thread and that thread must be the first thread in the process. Please run the JVM with -XstartOnFirstThread.
```

### 3.2 Upgrade LWJGL from `3.2.1` to `3.3.1`

Command:

```bash
perl -0pi -e 's/3\.2\.1/3.3.1/g' \
  .venv/lib/python3.10/site-packages/minerl/MCP-Reborn/build.gradle
```

Manual edit:

```text
.venv/lib/python3.10/site-packages/minerl/MCP-Reborn/build.gradle
```

Replace every LWJGL dependency version:

```text
3.2.1
```

with:

```text
3.3.1
```

This is required because LWJGL `3.2.1` is unstable on Apple Silicon macOS in this MineRL runtime. The crash can look like:

```text
SIGSEGV
Problematic frame: liblwjgl_stb.dylib
Current thread: Sound engine
```

### 3.3 Disable `checkGlfwError`

Command:

```bash
perl -0pi -e 's/public static void checkGlfwError\(BiConsumer<Integer, String> glfwErrorConsumer\) \{.*?\n   \}/public static void checkGlfwError(BiConsumer<Integer, String> glfwErrorConsumer) {\n   }/s' \
  .venv/lib/python3.10/site-packages/minerl/MCP-Reborn/src/main/java/net/minecraft/client/MainWindow.java
```

Manual edit:

```text
.venv/lib/python3.10/site-packages/minerl/MCP-Reborn/src/main/java/net/minecraft/client/MainWindow.java
```

Change this method so the method body is empty:

```java
public static void checkGlfwError(BiConsumer<Integer, String> glfwErrorConsumer) {
}
```

This avoids a macOS GLFW initialization error path that can stop the environment before MineRL finishes startup.

### 3.4 Disable `glfwSetWindowIcon`

Command:

```bash
perl -0pi -e 's/^\s*GLFW\.glfwSetWindowIcon\(this\.handle, buffer\);/         \/\/ GLFW.glfwSetWindowIcon(this.handle, buffer);/m' \
  .venv/lib/python3.10/site-packages/minerl/MCP-Reborn/src/main/java/net/minecraft/client/MainWindow.java
```

Manual edit:

```text
.venv/lib/python3.10/site-packages/minerl/MCP-Reborn/src/main/java/net/minecraft/client/MainWindow.java
```

Comment out this line:

```java
GLFW.glfwSetWindowIcon(this.handle, buffer);
```

so it becomes:

```java
// GLFW.glfwSetWindowIcon(this.handle, buffer);
```

This avoids another GLFW/macOS call that is not needed for MineRL and can fail during window initialization.

### 3.5 Disable `SoundEngine`

Manual edit:

```text
.venv/lib/python3.10/site-packages/minerl/MCP-Reborn/src/main/java/net/minecraft/client/audio/SoundEngine.java
```

Change `private synchronized void load()` so it does not initialize OpenAL or preload sounds:

```java
private synchronized void load() {
   if (!this.loaded) {
      this.soundsToPreload.clear();
      LOGGER.info(LOG_MARKER, "Sound engine disabled for MineRL Apple Silicon compatibility");

   }
}
```

This fixes JVM crashes like:

```text
SIGSEGV
Problematic frame: liblwjgl_stb.dylib
Current thread: Sound engine
```

When this happens, Python can report:

```text
TypeError: a bytes-like object is required, not 'NoneType'
```

That Python error means Minecraft crashed before replying to MineRL's mission init request.

### 3.6 Initialize `HumanPlayInterface` mouse state before event dispatch

Manual edit:

```text
.venv/lib/python3.10/site-packages/minerl/human_play_interface/human_play_interface.py
```

Move these assignments above the `self.window.on_mouse_motion = self._on_mouse_motion` handler registration:

```python
self.last_pov = None
self.last_mouse_delta = [0, 0]
```

This fixes:

```text
AttributeError: '_SingleAgentEnv' object has no attribute 'last_mouse_delta'
```

Pyglet can dispatch a mouse-move event during `HumanPlayInterface.__init__`. If that happens before `last_mouse_delta` exists on the wrapper, Gym delegates the missing attribute lookup to the wrapped MineRL environment and raises this error.

### 3.7 Check the edits

```bash
grep -n 'XstartOnFirstThread' \
  .venv/lib/python3.10/site-packages/minerl/MCP-Reborn/launchClient.sh

grep -nE '3\.3\.1|checkGlfwError|glfwSetWindowIcon|Sound engine disabled' \
  .venv/lib/python3.10/site-packages/minerl/MCP-Reborn/build.gradle \
  .venv/lib/python3.10/site-packages/minerl/MCP-Reborn/src/main/java/net/minecraft/client/MainWindow.java \
  .venv/lib/python3.10/site-packages/minerl/MCP-Reborn/src/main/java/net/minecraft/client/audio/SoundEngine.java

grep -n 'last_mouse_delta' \
  .venv/lib/python3.10/site-packages/minerl/human_play_interface/human_play_interface.py
```

These checks should show the patched launcher line, LWJGL `3.3.1`, the empty `checkGlfwError` method, the commented `glfwSetWindowIcon` call, the disabled SoundEngine log message, and early mouse state initialization.

### 3.8 Rebuild the jar

```bash
cd .venv/lib/python3.10/site-packages/minerl/MCP-Reborn
./gradlew clean build shadowJar
cd -
```

Rebuilding is required because the LWJGL, `MainWindow.java`, and `SoundEngine.java` edits affect the Java/Minecraft artifact that MineRL launches.

Before rebuilding, a clean environment can still fail with:

```text
GLFW error 65544: Cocoa: Failed to find service port for display.
```

The first reset can still take tens of seconds because MineRL starts a full Minecraft runtime.

## References

- MineRL tutorial docs: https://minerl.readthedocs.io/en/latest/tutorials/index.html
- MineRL macOS issue comment: https://github.com/minerllabs/minerl/issues/659#issuecomment-1306635414
- Homebrew `temurin@8` cask: https://formulae.brew.sh/cask/temurin%408
