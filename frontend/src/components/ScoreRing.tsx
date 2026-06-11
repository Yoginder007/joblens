"use client";

import { useId } from "react";
import { motion } from "framer-motion";
import AnimatedNumber from "./AnimatedNumber";

interface ScoreRingProps {
  value: number; // 0–100
  size?: number;
}

function tierColors(score: number): [string, string] {
  if (score >= 80) return ["#10b981", "#34d399"]; // emerald
  if (score >= 50) return ["#f59e0b", "#fbbf24"]; // amber
  return ["#f43f5e", "#fb7185"]; // rose
}

/** Animated circular match-score gauge (sweeps in on mount). */
export default function ScoreRing({ value, size = 54 }: ScoreRingProps) {
  const gradId = useId();
  const [from, to] = tierColors(value);
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = size / 2;

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={from} />
            <stop offset="100%" stopColor={to} />
          </linearGradient>
        </defs>
        <circle cx={c} cy={c} r={r} fill="none" strokeWidth={stroke}
          className="stroke-fg/10" />
        <motion.circle
          cx={c} cy={c} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round"
          stroke={`url(#${gradId})`}
          initial={{ pathLength: 0 }}
          animate={{ pathLength: Math.max(0.02, Math.min(value, 100) / 100) }}
          transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold text-fg tabular-nums">
        <AnimatedNumber value={value} />
      </span>
    </div>
  );
}
