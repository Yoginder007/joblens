"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

interface UserMenuProps {
  authed: boolean;
  email?: string;
  fullName?: string;
  onLogin: () => void;
  onSignup: () => void;
  onSignOut: () => void;
}

function initials(name?: string, email?: string): string {
  const src = (name || email || "?").trim();
  const parts = src.split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}

/**
 * Header account control. Signed out → "Log in" / "Sign up" buttons.
 * Signed in → animated avatar that opens a dropdown (email + sign out).
 */
export default function UserMenu({ authed, email, fullName, onLogin, onSignup, onSignOut }: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  if (!authed) {
    return (
      <div className="flex items-center gap-2">
        <button onClick={onLogin}
          className="px-3 py-2 rounded-xl text-xs font-semibold text-fg/70 hover:text-fg transition-colors">
          Log in
        </button>
        <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }} onClick={onSignup}
          className="px-4 py-2 rounded-xl text-xs font-bold on-accent bg-accent">
          Sign up
        </motion.button>
      </div>
    );
  }

  return (
    <div ref={ref} className="relative">
      <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
        onClick={() => setOpen((o) => !o)} aria-label="Account menu"
        className="w-9 h-9 rounded-xl bg-accent flex items-center justify-center text-[11px] font-bold on-accent">
        {initials(fullName, email)}
      </motion.button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.96 }}
            transition={{ type: "spring", stiffness: 420, damping: 30 }}
            className="absolute right-0 mt-2 w-56 glass-popover rounded-2xl p-2 origin-top-right z-50"
          >
            <div className="px-3 py-2.5 border-b border-fg/10 mb-1">
              <p className="text-xs font-semibold text-fg truncate">{fullName || "Your account"}</p>
              <p className="text-[11px] text-fg/50 truncate">{email}</p>
            </div>
            <button onClick={() => { setOpen(false); onSignOut(); }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-fg/70 hover:bg-fg/[0.06] hover:text-destructive transition-colors">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
