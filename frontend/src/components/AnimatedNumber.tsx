"use client";

import { useEffect } from "react";
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "framer-motion";

interface AnimatedNumberProps {
  value: number;
  decimals?: number;
  suffix?: string;
  duration?: number;
}

export default function AnimatedNumber({
  value,
  decimals = 0,
  suffix = "",
  duration = 1.1,
}: AnimatedNumberProps) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(reduce ? value : 0);
  const text = useTransform(mv, (v) => v.toFixed(decimals));

  useEffect(() => {
    if (reduce) {
      mv.set(value);
      return;
    }
    const controls = animate(mv, value, { duration, ease: [0.16, 1, 0.3, 1] });
    return () => controls.stop();
  }, [value, duration, reduce, mv]);

  return (
    <span className="tabular-nums">
      <motion.span>{text}</motion.span>
      {suffix}
    </span>
  );
}
