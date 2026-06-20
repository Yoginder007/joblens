/* Shared framer-motion variants for cinematic, consistent reveals.
 * All respect prefers-reduced-motion automatically via framer-motion's
 * MotionConfig / useReducedMotion where used. */
import type { Variants } from "framer-motion";

const EASE = [0.19, 1, 0.22, 1] as const; // expo-out (matches --ease-enter from developers.openai.com)

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

/** Tab/phase swap transition for AnimatePresence mode="wait".
 *
 * Deliberately NO `filter` animation: animating blur is GPU-expensive and a
 * lingering `filter` turns the container into the containing block for
 * position:fixed descendants (it once pinned the mobile drawer off-screen).
 * The exit is kept very short — with mode="wait" the exit duration is dead
 * time where neither view is on screen. */
export const swap: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: EASE } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.12, ease: "easeIn" } },
};
