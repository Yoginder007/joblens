"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { BackendStatus } from "@/lib/useBackendStatus";

const MESSAGES = [
  "Contacting the server…",
  "Waking the free-tier server — cold starts can take up to a minute.",
  "Still warming up… almost there.",
  "Loading the job catalogue…",
];

/**
 * Full-panel state shown while the free-tier backend cold-starts: pulsing
 * logo with orbiting dots, rotating status lines, and a live elapsed timer so
 * the wait reads as progress instead of a broken page. Respects the global
 * MotionConfig reducedMotion="user".
 */
export default function BackendWakingScreen({
  status,
  sinceMs,
}: {
  status: BackendStatus;
  sinceMs: number;
}) {
  const [elapsed, setElapsed] = useState(0);
  const [msgIdx, setMsgIdx] = useState(0);

  useEffect(() => {
    const tick = setInterval(
      () => setElapsed(Math.max(0, Math.round((Date.now() - sinceMs) / 1000))),
      1000
    );
    return () => clearInterval(tick);
  }, [sinceMs]);

  useEffect(() => {
    const rotate = setInterval(() => setMsgIdx((i) => (i + 1) % MESSAGES.length), 4500);
    return () => clearInterval(rotate);
  }, []);

  const down = status === "down";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="max-w-md mx-auto"
    >
      <div className="p-10 border border-border rounded-2xl bg-card shadow-sm text-center">
        {/* Pulsing logo + orbiting dots */}
        <div className="relative w-20 h-20 mx-auto mb-8">
          <motion.div
            className="absolute inset-3 rounded-xl bg-primary flex items-center justify-center"
            animate={down ? {} : { scale: [1, 1.08, 1], opacity: [1, 0.85, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          >
            <svg className="w-6 h-6 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <circle cx="11" cy="11" r="3" strokeWidth={2} />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16.5 16.5L21 21" />
            </svg>
          </motion.div>
          {!down && (
            <motion.div
              className="absolute inset-0"
              animate={{ rotate: 360 }}
              transition={{ duration: 3.5, repeat: Infinity, ease: "linear" }}
            >
              {[0, 120, 240].map((deg) => (
                <span
                  key={deg}
                  className="absolute w-1.5 h-1.5 rounded-full bg-muted-foreground/60"
                  style={{
                    top: "50%",
                    left: "50%",
                    transform: `rotate(${deg}deg) translateX(38px) translateY(-50%)`,
                  }}
                />
              ))}
            </motion.div>
          )}
        </div>

        <h3 className="text-base font-semibold text-foreground mb-2">
          {down ? "The server is taking unusually long" : "Starting the backend"}
        </h3>

        {/* Rotating status line */}
        <div className="h-10 flex items-center justify-center px-4">
          <AnimatePresence mode="wait">
            <motion.p
              key={down ? "down" : msgIdx}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.3 }}
              className="text-sm text-muted-foreground leading-snug"
            >
              {down
                ? "We're still trying to reach it. You can wait here — the page continues retrying automatically."
                : MESSAGES[msgIdx]}
            </motion.p>
          </AnimatePresence>
        </div>

        {/* Indeterminate progress shimmer */}
        {!down && (
          <div className="mt-5 h-1 rounded-full bg-muted overflow-hidden" role="progressbar" aria-label="Backend starting">
            <motion.div
              className="h-full w-1/3 rounded-full bg-primary"
              animate={{ x: ["-120%", "320%"] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>
        )}

        <div className="mt-5 flex items-center justify-center gap-3 text-xs text-muted-foreground">
          <span className="tabular-nums font-mono">{elapsed}s elapsed</span>
          {elapsed > 45 && !down && (
            <span className="text-muted-foreground/80">free-tier cold starts are slow — hang tight</span>
          )}
        </div>

        {down && (
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-6 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Retry now
          </button>
        )}
      </div>

      <p className="text-center text-[11px] text-muted-foreground/70 mt-4">
        JobLens runs on a free tier that sleeps when idle — the first visit wakes it up.
      </p>
    </motion.div>
  );
}
