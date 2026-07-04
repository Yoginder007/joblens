"use client";

/* ─────────────────────────────────────────────────────────────────────────────
 * Backend liveness for free-tier hosting.
 *
 * The API sleeps when idle and a cold start takes 30–90s. This module pings
 * /api/health once per app load (module-level singleton — every consumer
 * shares one probe loop) and exposes the state as a hook:
 *
 *   checking → first ping in flight; render normally (warm backends answer
 *              fast, so nothing flashes)
 *   waking   → no successful ping within the grace window; show the waking
 *              screen while retrying every few seconds
 *   ready    → healthy; render the app (data fetches retry independently in
 *              lib/api.ts, so content pops in without a manual refresh)
 *   down     → still unreachable after the cap; keep probing quietly
 * ───────────────────────────────────────────────────────────────────────────── */

import { useSyncExternalStore } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type BackendStatus = "checking" | "waking" | "ready" | "down";

const GRACE_MS = 2_500; // warm backends answer within this — no waking flash
const RETRY_MS = 3_000;
const DOWN_AFTER_MS = 180_000; // 3 min: report "down" but keep probing
const DOWN_RETRY_MS = 15_000;

let status: BackendStatus = "checking";
let startedAt = 0;
let started = false;
const listeners = new Set<() => void>();

function setStatus(next: BackendStatus) {
  if (status === next) return;
  status = next;
  listeners.forEach((l) => l());
}

async function ping(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

function start() {
  if (started || typeof window === "undefined") return;
  started = true;
  startedAt = Date.now();

  const grace = setTimeout(() => {
    if (status === "checking") setStatus("waking");
  }, GRACE_MS);

  const attempt = async () => {
    if (await ping()) {
      clearTimeout(grace);
      setStatus("ready");
      return;
    }
    const elapsed = Date.now() - startedAt;
    if (elapsed > DOWN_AFTER_MS) {
      setStatus("down");
      setTimeout(attempt, DOWN_RETRY_MS);
    } else {
      setTimeout(attempt, RETRY_MS);
    }
  };
  void attempt();
}

function subscribe(onStoreChange: () => void): () => void {
  start(); // idempotent — first subscriber kicks off the probe loop
  listeners.add(onStoreChange);
  return () => {
    listeners.delete(onStoreChange);
  };
}

const getSnapshot = () => status;
const getServerSnapshot = (): BackendStatus => "checking";

export function useBackendStatus(): { status: BackendStatus; sinceMs: number } {
  const current = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  return { status: current, sinceMs: startedAt };
}
