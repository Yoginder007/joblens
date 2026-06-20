"use client";

import { motion } from "framer-motion";
import AnimatedNumber from "./AnimatedNumber";

interface ScoreRingProps {
  value: number; // 0–100
  size?: number;
}

/** Animated circular match-score gauge (sweeps in on mount). */
export default function ScoreRing({ value, size = 54 }: ScoreRingProps) {
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = size / 2;

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={c} cy={c} r={r} fill="none" strokeWidth={stroke}
          className="stroke-muted" />
        <motion.circle
          cx={c} cy={c} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round"
          className="stroke-primary"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: Math.max(0.02, Math.min(value, 100) / 100) }}
          transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold text-foreground tabular-nums">
        <AnimatedNumber value={value} />
      </span>
    </div>
  );
}
