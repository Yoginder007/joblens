"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import type { RecentJob } from "@/lib/api";
import JobDetailBody from "./JobDetailBody";

interface JobDetailDrawerProps {
  job: RecentJob | null;
  onClose: () => void;
}

/**
 * Slide-over panel showing a job's full detail (description, skills, meta) —
 * lets users read a posting without leaving the page (Naukri/Indeed style).
 * Used below the xl breakpoint; desktop uses the inline split-view pane.
 */
export default function JobDetailDrawer({ job, onClose }: JobDetailDrawerProps) {
  // Portal target exists only client-side.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  // Close on Escape; lock body scroll while open.
  useEffect(() => {
    if (!job) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [job, onClose]);

  if (!mounted) return null;

  // Portalled to <body>: ancestor transform/filter (e.g. the tab-swap blur)
  // would otherwise become the containing block for position:fixed and pin
  // the drawer off-screen.
  return createPortal(
    <AnimatePresence>
      {job && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
          />
          <motion.aside
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
            className="fixed top-0 right-0 z-50 h-full w-full max-w-lg overflow-y-auto glass-popover border-l border-fg/10"
          >
            <JobDetailBody job={job} onClose={onClose} />
          </motion.aside>
        </>
      )}
    </AnimatePresence>,
    document.body
  );
}
