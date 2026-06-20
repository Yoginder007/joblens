"use client";

import { useEffect, useState } from "react";
import { clearSession, getSession } from "@/lib/session";

interface AuthIdentity {
  email: string;
  full_name: string;
}

/**
 * Owns the account/auth slice that used to live inline in the home page:
 * whether a session is signed in, the account identity, and the login/signup
 * modal state. Hydrates once from localStorage on mount (client-only).
 */
export function useAuth() {
  const [authed, setAuthed] = useState(false);
  const [acctEmail, setAcctEmail] = useState<string | undefined>();
  const [acctName, setAcctName] = useState<string | undefined>();
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");

  useEffect(() => {
    // localStorage only exists on the client, so hydrate on mount.
    const s = getSession();
    if (s?.account) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAuthed(true);
      setAcctEmail(s.email);
      setAcctName(s.fullName);
    }
  }, []);

  const openAuth = (mode: "login" | "signup") => {
    setAuthMode(mode);
    setAuthOpen(true);
  };
  const closeAuth = () => setAuthOpen(false);

  const signIn = (user: AuthIdentity) => {
    setAuthed(true);
    setAcctEmail(user.email);
    setAcctName(user.full_name);
    setAuthOpen(false);
  };

  const signOut = () => {
    clearSession();
    setAuthed(false);
    setAcctEmail(undefined);
    setAcctName(undefined);
  };

  return { authed, acctEmail, acctName, authOpen, authMode, openAuth, closeAuth, signIn, signOut };
}
