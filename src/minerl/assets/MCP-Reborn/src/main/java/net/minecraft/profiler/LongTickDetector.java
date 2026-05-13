package net.minecraft.profiler;

import java.io.File;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.function.LongSupplier;
import javax.annotation.Nullable;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class LongTickDetector {
   private static final Logger field_233516_a_ = LogManager.getLogger();
   private final LongSupplier field_233517_b_ = null;
   private final long field_233518_c_ = 0L;
   private int tickCounter;
   private final File field_233520_e_ = null;
   private IResultableProfiler profiler;

   public IProfiler getProfiler() {
      this.profiler = new Profiler(this.field_233517_b_, () -> {
         return this.tickCounter;
      }, false);
      ++this.tickCounter;
      return this.profiler;
   }

   public void func_233525_b_() {
      if (this.profiler != EmptyProfiler.INSTANCE) {
         IProfileResult iprofileresult = this.profiler.getResults();
         this.profiler = EmptyProfiler.INSTANCE;
         if (iprofileresult.nanoTime() >= this.field_233518_c_) {
            File file1 = new File(this.field_233520_e_, "tick-results-" + (new SimpleDateFormat("yyyy-MM-dd_HH.mm.ss")).format(new Date()) + ".txt");
            iprofileresult.writeToFile(file1);
            field_233516_a_.info("Recorded long tick -- wrote info to: {}", (Object)file1.getAbsolutePath());
         }

      }
   }

   @Nullable
   public static LongTickDetector func_233524_a_(String p_233524_0_) {
      return null;
   }

   public static IProfiler getProfiler(IProfiler p_233523_0_, @Nullable LongTickDetector p_233523_1_) {
      return p_233523_1_ != null ? IProfiler.func_233513_a_(p_233523_1_.getProfiler(), p_233523_0_) : p_233523_0_;
   }

   private LongTickDetector() {
      throw new RuntimeException("Synthetic constructor added by MCP, do not call");
   }
}
