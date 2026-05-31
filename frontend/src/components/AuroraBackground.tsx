"use client";

import { useEffect } from "react";
import { motion, useMotionValue, useSpring, useTransform, useReducedMotion } from "framer-motion";

/**
 * Animated aurora background with subtle cursor parallax. Each blob already
 * drifts on its own CSS keyframe; on top of that we nudge the whole field
 * toward the pointer via springs, which reads as organic depth rather than a
 * rigid follow. Fully disabled under prefers-reduced-motion.
 */
export default function AuroraBackground() {
  const reduce = useReducedMotion();
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const sx = useSpring(mx, { stiffness: 40, damping: 20 });
  const sy = useSpring(my, { stiffness: 40, damping: 20 });

  // Different parallax depths per layer for a layered, 3D-ish feel.
  const x1 = useTransform(sx, (v) => v * 28);
  const y1 = useTransform(sy, (v) => v * 28);
  const x2 = useTransform(sx, (v) => v * -36);
  const y2 = useTransform(sy, (v) => v * -22);
  const x3 = useTransform(sx, (v) => v * 18);
  const y3 = useTransform(sy, (v) => v * -30);

  useEffect(() => {
    if (reduce) return;
    const onMove = (e: MouseEvent) => {
      // Normalise pointer to [-0.5, 0.5] around viewport centre.
      mx.set(e.clientX / window.innerWidth - 0.5);
      my.set(e.clientY / window.innerHeight - 0.5);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [mx, my, reduce]);

  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
      <motion.div style={reduce ? undefined : { x: x1, y: y1 }}
        className="aurora-blob animate-aurora-1 w-[55vw] h-[55vw] -top-[15%] -left-[10%] bg-indigo-600/40" />
      <motion.div style={reduce ? undefined : { x: x2, y: y2 }}
        className="aurora-blob animate-aurora-2 w-[50vw] h-[50vw] top-[10%] right-[-15%] bg-fuchsia-600/30" />
      <motion.div style={reduce ? undefined : { x: x3, y: y3 }}
        className="aurora-blob animate-aurora-3 w-[45vw] h-[45vw] bottom-[-20%] left-[20%] bg-violet-600/30" />
      <div className="grid-overlay" />
      <div className="noise-overlay" />
      <div className="aurora-veil" />
    </div>
  );
}
