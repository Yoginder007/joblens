/* Shared framer-motion variants for cinematic, consistent reveals.
 * All respect prefers-reduced-motion automatically via framer-motion's
 * MotionConfig / useReducedMotion where used. */
import type { Variants } from "framer-motion";

const EASE = [0.16, 1, 0.3, 1] as const; // expo-out

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: EASE } },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.5, ease: EASE } },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  show: { opacity: 1, scale: 1, transition: { duration: 0.45, ease: EASE } },
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 18, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.5, ease: EASE } },
};

export function staggerContainer(stagger = 0.07, delayChildren = 0): Variants {
  return {
    hidden: {},
    show: { transition: { staggerChildren: stagger, delayChildren } },
  };
}

/** Tab/phase swap transition for AnimatePresence mode="wait". */
export const swap: Variants = {
  hidden: { opacity: 0, y: 12, filter: "blur(4px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.4, ease: EASE } },
  exit: { opacity: 0, y: -12, filter: "blur(4px)", transition: { duration: 0.25, ease: EASE } },
};
