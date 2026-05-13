package net.minecraft.profiler;

import java.util.function.IntSupplier;
import java.util.function.LongSupplier;

public class TimeTracker {
   private final LongSupplier nanoTimeSupplier;
   private final IntSupplier tickSupplier;
   private IResultableProfiler profiler = EmptyProfiler.INSTANCE;

   public TimeTracker(LongSupplier nanoTimeSupplier, IntSupplier tickSupplier) {
      this.nanoTimeSupplier = nanoTimeSupplier;
      this.tickSupplier = tickSupplier;
   }

   public boolean isTracking() {
      return this.profiler != EmptyProfiler.INSTANCE;
   }

   public void stopTracking() {
      this.profiler = EmptyProfiler.INSTANCE;
   }

   public void startTracking() {
      this.profiler = new Profiler(this.nanoTimeSupplier, this.tickSupplier, true);
   }

   public IProfiler getProfiler() {
      return this.profiler;
   }

   public IProfileResult getResults() {
      return this.profiler.getResults();
   }
}
