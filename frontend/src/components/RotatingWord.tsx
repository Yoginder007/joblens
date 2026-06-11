"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

interface RotatingWordProps {
  words: string[];
  /** ms between swaps */
  interval?: number;
  className?: string;
}

/**
 * Cycles through words with a vertical mask swap. All words are stacked in the
 * same grid cell, so the container width never changes — the centered headline
 * stays perfectly stable while the word animates.
 */
export default function RotatingWord({ words, interval = 2600, className = "" }: RotatingWordProps) {
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (words.length < 2) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % words.length), interval);
    return () => clearInterval(t);
  }, [words.length, interval]);

  return (
    <span className="relative inline-grid justify-items-center overflow-hidden align-bottom">
      {words.map((w, i) => (
        <motion.span
          key={w}
          aria-hidden={i !== idx}
          initial={false}
          animate={
            i === idx
              ? { y: "0%", opacity: 1, filter: "blur(0px)" }
              : { y: i === (idx + words.length - 1) % words.length ? "-105%" : "105%", opacity: 0, filter: "blur(6px)" }
          }
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          className={`col-start-1 row-start-1 whitespace-nowrap ${className}`}
        >
          {w}
        </motion.span>
      ))}
    </span>
  );
}
