package net.minecraft.server;

import com.google.common.base.Charsets;
import java.io.IOException;
import java.nio.Buffer;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.api.distmarker.OnlyIn;

public class SessionLockManager implements AutoCloseable {
   private final FileChannel fileChannel;
   private final FileLock fileLock;
   private static final ByteBuffer BYTE_BUFFER;

   public static SessionLockManager getDirLock(Path p) throws IOException {
      Path path = p.resolve("session.lock");
      if (!Files.isDirectory(p)) {
         Files.createDirectories(p);
      }

      FileChannel filechannel = FileChannel.open(path, StandardOpenOption.CREATE, StandardOpenOption.WRITE);

      try {
         filechannel.write(BYTE_BUFFER.duplicate());
         filechannel.force(true);
         FileLock filelock = filechannel.tryLock();
         if (filelock == null) {
            throw SessionLockManager.AlreadyLockedException.func_233000_a_(path);
         } else {
            return new SessionLockManager(filechannel, filelock);
         }
      } catch (IOException ioexception1) {
         try {
            filechannel.close();
         } catch (IOException ioexception) {
            ioexception1.addSuppressed(ioexception);
         }

         throw ioexception1;
      }
   }

   private SessionLockManager(FileChannel fileChannel, FileLock fileLock) {
      this.fileChannel = fileChannel;
      this.fileLock = fileLock;
   }

   public void close() throws IOException {
      try {
         if (this.fileLock.isValid()) {
            this.fileLock.release();
         }
      } finally {
         if (this.fileChannel.isOpen()) {
            this.fileChannel.close();
         }

      }

   }

   public boolean isLockValid() {
      return this.fileLock.isValid();
   }

   @OnlyIn(Dist.CLIENT)
   public static boolean isUnlocked(Path p) throws IOException {
      Path path = p.resolve("session.lock");

      try (
         FileChannel filechannel = FileChannel.open(path, StandardOpenOption.WRITE);
         FileLock filelock = filechannel.tryLock();
      ) {
         return filelock == null;
      } catch (AccessDeniedException accessdeniedexception) {
         return true;
      } catch (NoSuchFileException nosuchfileexception) {
         return false;
      }
   }

   static {
      byte[] abyte = "\u2603".getBytes(Charsets.UTF_8);
      BYTE_BUFFER = ByteBuffer.allocateDirect(abyte.length);
      BYTE_BUFFER.put(abyte);
      ((Buffer) BYTE_BUFFER).flip();
   }

   public static class AlreadyLockedException extends IOException {
      private AlreadyLockedException(Path p_i231438_1_, String p_i231438_2_) {
         super(p_i231438_1_.toAbsolutePath() + ": " + p_i231438_2_);
      }

      public static SessionLockManager.AlreadyLockedException func_233000_a_(Path p_233000_0_) {
         return new SessionLockManager.AlreadyLockedException(p_233000_0_, "already locked (possibly by other Minecraft instance?)");
      }
   }
}
