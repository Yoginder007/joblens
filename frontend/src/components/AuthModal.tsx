"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { login, signup, type CandidateCreated } from "@/lib/api";
import { setSession } from "@/lib/session";

interface AuthModalProps {
  open: boolean;
  initialMode?: "login" | "signup";
  onClose: () => void;
  onAuthed: (user: CandidateCreated) => void;
}

/**
 * Animated login / signup modal. Tab toggle slides a pill between the two modes;
 * the form fields cross-fade; password has a show/hide; errors animate in.
 */
export default function AuthModal({ open, initialMode = "login", onClose, onAuthed }: AuthModalProps) {
  const [mode, setMode] = useState<"login" | "signup">(initialMode);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Reset mode/error when the modal (re)opens — intentional sync from props.
    if (open) {
      /* eslint-disable react-hooks/set-state-in-effect */
      setMode(initialMode);
      setError(null);
      /* eslint-enable react-hooks/set-state-in-effect */
    }
  }, [open, initialMode]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  const submit = async () => {
    setError(null);
    if (!email || !password || (mode === "signup" && !fullName)) {
      setError("Please fill in all fields.");
      return;
    }
    if (mode === "signup" && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      const user = mode === "signup"
        ? await signup(email, fullName, password)
        : await login(email, password);
      setSession({
        token: user.access_token,
        candidateId: user.id,
        email: user.email,
        fullName: user.full_name,
        account: true,
      });
      onAuthed(user);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
            <motion.div
              initial={{ opacity: 0, y: 24, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 24, scale: 0.96 }}
              transition={{ type: "spring", stiffness: 320, damping: 28 }}
              className="pointer-events-auto w-full max-w-md glass-popover rounded-3xl p-7 relative overflow-hidden"
            >
              <div className="absolute -top-20 -right-20 w-52 h-52 rounded-full bg-violet-600/20 blur-3xl pointer-events-none" />

              {/* Header */}
              <div className="relative flex items-center justify-between mb-6">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-accent flex items-center justify-center shadow-[0_0_18px_rgba(139,92,246,0.5)]">
                    <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <circle cx="11" cy="11" r="7" strokeWidth={2} strokeDasharray="3 3" />
                      <circle cx="11" cy="11" r="3" strokeWidth={2} />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16.5 16.5L21 21" />
                    </svg>
                  </div>
                  <span className="font-extrabold tracking-tight text-fg">JobLens</span>
                </div>
                <button onClick={onClose} aria-label="Close"
                  className="w-8 h-8 rounded-lg glass glass-hover flex items-center justify-center">
                  <svg className="w-4 h-4 text-fg/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Mode toggle */}
              <div className="relative flex bg-fg/[0.05] rounded-xl p-1 mb-6">
                {(["login", "signup"] as const).map((m) => (
                  <button key={m} type="button" onClick={() => { setMode(m); setError(null); }}
                    className={`relative flex-1 py-2 rounded-lg text-xs font-bold z-10 transition-colors ${
                      mode === m ? "on-accent" : "text-fg/50 hover:text-fg/80"
                    }`}>
                    {mode === m && (
                      <motion.div layoutId="authPill" className="absolute inset-0 bg-accent rounded-lg -z-10"
                        transition={{ type: "spring", stiffness: 380, damping: 30 }} />
                    )}
                    {m === "login" ? "Log In" : "Sign Up"}
                  </button>
                ))}
              </div>

              {/* Fields */}
              <div className="space-y-3" onKeyDown={(e) => { if (e.key === "Enter") submit(); }}>
                <AnimatePresence initial={false} mode="popLayout">
                  {mode === "signup" && (
                    <motion.input
                      key="name"
                      initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                      type="text" value={fullName} onChange={(e) => setFullName(e.target.value)}
                      placeholder="Full name" className="input-glass" autoFocus
                    />
                  )}
                </AnimatePresence>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com" className="input-glass" />
                <div className="relative">
                  <input type={showPw ? "text" : "password"} value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={mode === "signup" ? "Password (min 8 chars)" : "Password"}
                    className="input-glass pr-10" />
                  <button type="button" onClick={() => setShowPw((s) => !s)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-fg/40 hover:text-fg/70"
                    aria-label={showPw ? "Hide password" : "Show password"}>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      {showPw
                        ? <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88L3 3m6.88 6.88L21 21" />
                        : <><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></>}
                    </svg>
                  </button>
                </div>

                <AnimatePresence>
                  {error && (
                    <motion.p
                      initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                      className="text-xs text-rose-500 dark:text-rose-300">{error}</motion.p>
                  )}
                </AnimatePresence>

                <motion.button
                  whileHover={{ scale: busy ? 1 : 1.01 }} whileTap={{ scale: busy ? 1 : 0.99 }}
                  onClick={submit} disabled={busy}
                  className="w-full py-3 rounded-2xl text-sm font-bold on-accent bg-accent mt-1
                             shadow-[0_10px_40px_-8px_rgba(139,92,246,0.6)] transition-all
                             disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-[0_14px_50px_-8px_rgba(139,92,246,0.8)]">
                  {busy
                    ? <span className="inline-flex items-center gap-2"><svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>{mode === "signup" ? "Creating account…" : "Logging in…"}</span>
                    : (mode === "signup" ? "Create account" : "Log in")}
                </motion.button>
              </div>

              <p className="text-[11px] text-fg/40 text-center mt-4">
                {mode === "login" ? "New here? " : "Already have an account? "}
                <button onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(null); }}
                  className="text-violet-500 dark:text-violet-300 font-semibold hover:underline">
                  {mode === "login" ? "Create an account" : "Log in"}
                </button>
              </p>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
