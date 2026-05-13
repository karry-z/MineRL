from __future__ import annotations

from pathlib import Path

from minerl.tools.patch_minecraft import patch_minecraft_tree


def test_patch_minecraft_tree_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path
    window = root / "src/main/java/net/minecraft/client/MainWindow.java"
    sound = root / "src/main/java/net/minecraft/client/audio/SoundEngine.java"
    window.parent.mkdir(parents=True)
    sound.parent.mkdir(parents=True)
    (root / "launchClient.sh").write_text(
        "java -Xmx$maxMem -jar $fatjar --envPort=$port\n"
    )
    (root / "build.gradle").write_text(
        "repositories { jcenter() }\ncompile group: 'org.lwjgl', name: 'lwjgl', version: '3.2.1'\n"
    )
    window.write_text(
        """
public class MainWindow {
   public static void checkGlfwError(BiConsumer<Integer, String> glfwErrorConsumer) {
      throw new RuntimeException();
   }
   void icon() {
      GLFW.glfwSetWindowIcon(this.handle, buffer);
   }
}
"""
    )
    sound.write_text(
        """
public class SoundEngine {
   private synchronized void load() {
      this.loaded = true;
   }
}
"""
    )

    changed = patch_minecraft_tree(root)
    assert len(changed) == 4
    assert patch_minecraft_tree(root) == []
    assert "-XstartOnFirstThread" in (root / "launchClient.sh").read_text()
    assert "3.3.1" in (root / "build.gradle").read_text()
    assert "jcenter()" not in (root / "build.gradle").read_text()
    assert "glfwSetWindowIcon" in window.read_text()
    assert "Sound engine disabled" in sound.read_text()
