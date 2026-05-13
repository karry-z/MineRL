package net.minecraft.client;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

import net.minecraft.client.gui.IGuiEventListener;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.settings.KeyBinding;
import net.minecraft.client.util.InputMappings;
import net.minecraft.client.util.MouseSmoother;
import net.minecraft.client.util.NativeUtil;
import net.minecraft.util.math.MathHelper;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.api.distmarker.OnlyIn;
import org.lwjgl.glfw.GLFWDropCallback;

@OnlyIn(Dist.CLIENT)
public class MouseHelper {
   private final Minecraft minecraft;
   private boolean leftDown;
   private boolean middleDown;
   private boolean rightDown;
   private double mouseX;
   private double mouseY;
   private int simulatedRightClicks;
   private int activeButton = -1;
   private boolean ignoreFirstMove = true;
   private int touchScreenCounter;
   private double eventTime;
   private final MouseSmoother xSmoother = new MouseSmoother();
   private final MouseSmoother ySmoother = new MouseSmoother();
   private double xVelocity;
   private double yVelocity;
   private double accumulatedScrollDelta;
   private double lastLookTime = Double.MIN_VALUE;
   private boolean mouseGrabbed;
   private double dx = 0;
   private double dy = 0;
   private double accumDwheel = 0;
   private boolean humanInput = true;

   private Set<Integer> buttonsPressed = new HashSet<>();
   private Set<Integer> accumButtonsPressed = new HashSet<>();
   private Set<Integer> buttonsNewlyPressed = new HashSet<>();

   public MouseHelper(Minecraft minecraftIn) {
      this.minecraft = minecraftIn;
   }

   void mouseButtonCallback(long handle, int button, int action, int mods) {
      if (handle == minecraft.getMainWindow().getHandle()) {
         if (humanInput) {
            mouseButtonCallbackImpl(handle, button, action, mods);
         }
      }
      if (action == 1) {
         this.buttonsPressed.add(button);
         this.accumButtonsPressed.add(button);
         this.buttonsNewlyPressed.add(button);
      } else if (action == 0) {
         this.buttonsPressed.remove(button);
      } else {
         throw new RuntimeException("Unknown action! " + action);
      }
   }
   void mouseButtonCallbackImpl(long handle, int button, int action, int mods) {
      boolean flag = action == 1;
      if (Minecraft.IS_RUNNING_ON_MAC && button == 0) {
         if (flag) {
            if ((mods & 2) == 2) {
               button = 1;
               ++this.simulatedRightClicks;
            }
         } else if (this.simulatedRightClicks > 0) {
            button = 1;
            --this.simulatedRightClicks;
         }
      }

      int i = button;
      if (flag) {
         if (this.minecraft.gameSettings.touchscreen && this.touchScreenCounter++ > 0) {
            return;
         }

         this.activeButton = i;
         this.eventTime = NativeUtil.getTime();
      } else if (this.activeButton != -1) {
         if (this.minecraft.gameSettings.touchscreen && --this.touchScreenCounter > 0) {
            return;
         }

         this.activeButton = -1;
      }

      boolean[] aboolean = new boolean[]{false};
      if (this.minecraft.loadingGui == null) {
         if (this.minecraft.currentScreen == null) {
            if (!this.mouseGrabbed && flag) {
               this.grabMouse();
            }
         } else {
            double d0 = this.mouseX * (double)this.minecraft.getMainWindow().getScaledWidth() / (double)this.minecraft.getMainWindow().getWidth();
            double d1 = this.mouseY * (double)this.minecraft.getMainWindow().getScaledHeight() / (double)this.minecraft.getMainWindow().getHeight();
            if (flag) {
               Screen.wrapScreenError(() -> {
                  aboolean[0] = this.minecraft.currentScreen.mouseClicked(d0, d1, i);
               }, "mouseClicked event handler", this.minecraft.currentScreen.getClass().getCanonicalName());
            } else {
               Screen.wrapScreenError(() -> {
                  aboolean[0] = this.minecraft.currentScreen.mouseReleased(d0, d1, i);
               }, "mouseReleased event handler", this.minecraft.currentScreen.getClass().getCanonicalName());
            }
         }
      }

      if (!aboolean[0] && (this.minecraft.currentScreen == null || this.minecraft.currentScreen.passEvents) && this.minecraft.loadingGui == null) {
         if (i == 0) {
            this.leftDown = flag;
         } else if (i == 2) {
            this.middleDown = flag;
         } else if (i == 1) {
            this.rightDown = flag;
         }

         KeyBinding.setKeyBindState(InputMappings.Type.MOUSE.getOrMakeInput(i), flag);
         if (flag) {
            if (this.minecraft.player.isSpectator() && i == 2) {
               this.minecraft.ingameGUI.getSpectatorGui().onMiddleClick();
            } else {
               KeyBinding.onTick(InputMappings.Type.MOUSE.getOrMakeInput(i));
            }
         }
      }
   }

   void scrollCallback(long handle, double xoffset, double yoffset) {
      if (handle == minecraft.getMainWindow().getHandle()) {
         if (humanInput) {
            scrollCallbackImpl(handle, xoffset, yoffset);
         }
      }
      this.accumDwheel += yoffset;
   }

   void scrollCallbackImpl(long handle, double xoffset, double yoffset) {
      double d0 = (this.minecraft.gameSettings.discreteMouseScroll ? Math.signum(yoffset) : yoffset) * this.minecraft.gameSettings.mouseWheelSensitivity;
      if (this.minecraft.loadingGui == null) {
         if (this.minecraft.currentScreen != null) {
            double d1 = this.mouseX * (double) this.minecraft.getMainWindow().getScaledWidth() / (double) this.minecraft.getMainWindow().getWidth();
            double d2 = this.mouseY * (double) this.minecraft.getMainWindow().getScaledHeight() / (double) this.minecraft.getMainWindow().getHeight();
            this.minecraft.currentScreen.mouseScrolled(d1, d2, d0);
         } else if (this.minecraft.player != null) {
            if (this.accumulatedScrollDelta != 0.0D && Math.signum(d0) != Math.signum(this.accumulatedScrollDelta)) {
               this.accumulatedScrollDelta = 0.0D;
            }

            this.accumulatedScrollDelta += d0;
            float f1 = (float) ((int) this.accumulatedScrollDelta);
            if (f1 == 0.0F) {
               return;
            }

            this.accumulatedScrollDelta -= (double) f1;
            if (this.minecraft.player.isSpectator()) {
               if (this.minecraft.ingameGUI.getSpectatorGui().isMenuActive()) {
                  this.minecraft.ingameGUI.getSpectatorGui().onMouseScroll((double) (-f1));
               } else {
                  float f = MathHelper.clamp(this.minecraft.player.abilities.getFlySpeed() + f1 * 0.005F, 0.0F, 0.2F);
                  this.minecraft.player.abilities.setFlySpeed(f);
               }
            } else {
               this.minecraft.player.inventory.changeCurrentItem((double) f1);
            }
         }
      }
   }

   private void addPacksToScreen(long window, List<Path> paths) {
      if (this.minecraft.currentScreen != null) {
         this.minecraft.currentScreen.addPacks(paths);
      }

   }

   public void registerCallbacks(long handle) {
      if (minecraft.gameSettings.envPort != 0) {
         // if minecraft operates in the env mode (envPort != 0), we should not
         // interact with the mouse; hence, the callbacks are not registered.
         return;
      }
      InputMappings.setMouseCallbacks(handle, (handle_, xpos, ypos) -> {
         minecraft.execute(() -> {
            this.cursorPosCallback(handle_, xpos, ypos);
         });
      }, (handle_, button, action, mods) -> {
         minecraft.execute(() -> {
            this.mouseButtonCallback(handle_, button, action, mods);
         });
      }, (handle_, xoffset, yoffset) -> {
         minecraft.execute(() -> {
            this.scrollCallback(handle_, xoffset, yoffset);
         });
      }, (window, p_238227_3_, p_238227_4_) -> {
         Path[] apath = new Path[p_238227_3_];

         for(int i = 0; i < p_238227_3_; ++i) {
            apath[i] = Paths.get(GLFWDropCallback.getName(p_238227_4_, i));
         }

         this.minecraft.execute(() -> {
            this.addPacksToScreen(window, Arrays.asList(apath));
         });
      });
   }

   public void executeIfHuman(Runnable runnable) {
      if (this.humanInput) {
         this.minecraft.execute(runnable);
      }
   }

   void cursorPosCallback(long handle, double xpos, double ypos) {
      if (handle == minecraft.getMainWindow().getHandle()) {
         if (this.ignoreFirstMove) {
            this.mouseX = xpos;
            this.mouseY = ypos;
            this.ignoreFirstMove = false;
         }

         if (humanInput) {
            cursorPosCallbackImpl(xpos, ypos);
         } else {
            this.dx = xpos - this.mouseX;
            this.dy = ypos - this.mouseY;
         }
      }
   }

   void cursorPosCallbackImpl(double xpos, double ypos) {
      IGuiEventListener iguieventlistener = this.minecraft.currentScreen;
      if (iguieventlistener != null && this.minecraft.loadingGui == null) {
         double d0 = xpos * (double)this.minecraft.getMainWindow().getScaledWidth() / (double)this.minecraft.getMainWindow().getWidth();
         double d1 = ypos * (double)this.minecraft.getMainWindow().getScaledHeight() / (double)this.minecraft.getMainWindow().getHeight();
         Screen.wrapScreenError(() -> {
            iguieventlistener.mouseMoved(d0, d1);
         }, "mouseMoved event handler", iguieventlistener.getClass().getCanonicalName());
         if (this.activeButton != -1 && this.eventTime > 0.0D) {
            double d2 = (xpos - this.mouseX) * (double)this.minecraft.getMainWindow().getScaledWidth() / (double)this.minecraft.getMainWindow().getWidth();
            double d3 = (ypos - this.mouseY) * (double)this.minecraft.getMainWindow().getScaledHeight() / (double)this.minecraft.getMainWindow().getHeight();
            Screen.wrapScreenError(() -> {
               iguieventlistener.mouseDragged(d0, d1, this.activeButton, d2, d3);
            }, "mouseDragged event handler", iguieventlistener.getClass().getCanonicalName());
         }
      }

      this.minecraft.getProfiler().startSection("mouse");
      if (this.isMouseGrabbed() && this.minecraft.isGameFocused()) {
         this.xVelocity += xpos - this.mouseX;
         this.yVelocity += ypos - this.mouseY;
      }
      this.updatePlayerLook();
      this.minecraft.getProfiler().endSection();
      this.mouseX = xpos;
      this.mouseY = ypos;

   }

   public void updatePlayerLook() {
      double time = NativeUtil.getTime();
      double dt = time - this.lastLookTime;
      this.lastLookTime = time;
      if (true || this.isMouseGrabbed() && this.minecraft.isGameFocused()) {
         double d4 = this.minecraft.gameSettings.mouseSensitivity * (double)0.6F + (double)0.2F;
         double sensitivity = d4 * d4 * d4 * 8.0D;
         double yaw;
         double pitch;
         if (this.minecraft.gameSettings.smoothCamera) {
            double d6 = this.xSmoother.smooth(this.xVelocity * sensitivity, dt * sensitivity);
            double d7 = this.ySmoother.smooth(this.yVelocity * sensitivity, dt * sensitivity);
            yaw = d6;
            pitch = d7;
         } else {
            this.xSmoother.reset();
            this.ySmoother.reset();
            yaw = this.xVelocity * sensitivity;
            pitch = this.yVelocity * sensitivity;
         }
         double xvel = this.xVelocity;
         this.xVelocity = 0.0D;
         this.yVelocity = 0.0D;
         int i = 1;
         if (this.minecraft.gameSettings.invertMouse) {
            i = -1;
         }

         this.minecraft.getTutorial().onMouseMove(yaw, pitch);
         if (this.minecraft.player != null) {
            this.minecraft.player.rotateTowards(yaw, pitch * (double)i);
         }

      } else {
         this.xVelocity = 0.0D;
         this.yVelocity = 0.0D;
      }
   }

   public boolean isLeftDown() {
      return this.leftDown;
   }

   public boolean isRightDown() {
      return this.rightDown;
   }

   public double getMouseX() {
      return this.mouseX;
   }

   public double getMouseY() {
      return this.mouseY;
   }

   public boolean isMouseGrabbed() {
      return this.mouseGrabbed;
   }

   public void grabMouse() {
      if (this.minecraft.isGameFocused()) {
         if (!this.mouseGrabbed) {
            if (!Minecraft.IS_RUNNING_ON_MAC) {
               KeyBinding.updateKeyBindState();
            }

            this.mouseGrabbed = true;
            this.mouseX = (double)(this.minecraft.getMainWindow().getWidth() / 2);
            this.mouseY = (double)(this.minecraft.getMainWindow().getHeight() / 2);
            if (minecraft.gameSettings.envPort == 0) {
               InputMappings.setCursorPosAndMode(this.minecraft.getMainWindow().getHandle(), 212995, this.mouseX, this.mouseY);
            }
            this.minecraft.displayGuiScreen((Screen)null);
            this.minecraft.leftClickCounter = 10000;
            this.ignoreFirstMove = true;
         }
      }
   }

   public void ungrabMouse() {
      if (this.mouseGrabbed) {
         this.mouseGrabbed = false;
         this.mouseX = (double)(this.minecraft.getMainWindow().getWidth() / 2);
         this.mouseY = (double)(this.minecraft.getMainWindow().getHeight() / 2);
         if (minecraft.gameSettings.envPort == 0) {
            InputMappings.setCursorPosAndMode(this.minecraft.getMainWindow().getHandle(), 212993, this.mouseX, this.mouseY);
         }
      }
   }

   public void ignoreFirstMove() {
      this.ignoreFirstMove = true;
   }

   public State getState() {
      double scaleFactor = getScaleFactor();
      State state = new State(mouseX, mouseY, dx / scaleFactor, dy / scaleFactor, accumDwheel, accumButtonsPressed, buttonsNewlyPressed);
      dx = 0;
      dy = 0;
      accumDwheel = 0;
      accumButtonsPressed.retainAll(buttonsPressed);
      buttonsNewlyPressed.clear();
      return state;
   }

   private boolean isGuiOpen() {
      return Minecraft.getInstance().currentScreen != null;
   }

   public double getScaleFactor() {
      double scaleFactor = 1.0;
      if (isGuiOpen()) {
         Minecraft mc = Minecraft.getInstance();
         // this factor (ratio of framebuffer size to window size) would be 1 on normal screens,
         // but is 2 on retina screens. Such correction is needed, because
         // guiScale factor is defined wrt framebuffer size, mouse movements are calculated wrt window size
         double retinaFactor = mc.getFramebuffer().framebufferWidth / mc.getMainWindow().getWidth();
         scaleFactor = mc.getMainWindow().getGuiScaleFactor() / retinaFactor;
      }
      return scaleFactor;
   }

   public void clearState() {
      dx = 0;
      dy = 0;
      accumDwheel = 0;
      accumButtonsPressed.clear();
      buttonsPressed.clear();
      buttonsNewlyPressed.clear();
   }

   public boolean getHumanInput() {
      return humanInput;
   }

   public void setHumanInput(boolean humanInput) {
      this.humanInput = humanInput;
   }

   public static class State {
      public final double x;
      public final double y;
      public final double dx;
      public final double dy;
      public final double scaledX;
      public final double scaledY;
      public final double dwheel;
      public final Set<Integer> buttons;
      public final Set<Integer> newButtons;

      public State(double x, double y, double dx, double dy, double dwheel, Collection<Integer> buttons, Collection<Integer> newButtons) {
         MainWindow mw = Minecraft.getInstance().getMainWindow();
         MouseHelper mh = Minecraft.getInstance().mouseHelper;
         this.x = x;
         this.y = y;
         this.dx = dx;
         this.dy = dy;
         double scaleFactor = mh.getScaleFactor();
         this.scaledX = (x - mw.getWidth() / 2) / scaleFactor;
         this.scaledY = (y - mw.getHeight() / 2) / scaleFactor;
         this.dwheel = dwheel;
         this.buttons = new HashSet<>();
         this.buttons.addAll(buttons);
         this.newButtons = new HashSet<>();
         this.newButtons.addAll(newButtons);
      }
   }
}
