"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  createSubscription,
  listSubscriptions,
  deleteSubscription,
  type SearchFilters,
  type Subscription,
} from "@/lib/api";
import { getToken } from "@/lib/session";

interface JobAlertsProps {
  resumeId: string;
  filters: SearchFilters;
}

type Frequency = "instant" | "daily" | "weekly";

export default function JobAlerts({ resumeId, filters }: JobAlertsProps) {
  const [alerts, setAlerts] = useState<Subscription[]>([]);
  const [frequency, setFrequency] = useState<Frequency>("daily");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const token = getToken();

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      setAlerts(await listSubscriptions(token));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load alerts");
    }
  }, [token]);

  useEffect(() => {
    // Load existing alerts from the backend on mount (external system sync).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  const handleCreate = async () => {
    if (!token) {
      setError("Session expired — run a new search to re-authenticate.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await createSubscription(token, {
        resume_id: resumeId,
        frequency,
        channel: "email",
        filters: {
          location: filters.location,
          title_keyword: filters.title_keyword,
          sources: filters.sources,
        },
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create alert");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!token) return;
    try {
      await deleteSubscription(token, id);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete alert");
    }
  };

  const activeAlerts = alerts.filter((a) => a.is_active);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-2xl glass p-5 mb-8 relative overflow-hidden"
    >
      <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-violet-600/20 blur-3xl pointer-events-none" />

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 relative">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center flex-shrink-0 shadow-[0_0_18px_rgba(139,92,246,0.45)]">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-fg">Get Job Alerts</h3>
            <p className="text-xs text-fg/40 mt-0.5 max-w-md">
              We&apos;ll keep matching new postings to this résumé and email you the fresh ones.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <select value={frequency} onChange={(e) => setFrequency(e.target.value as Frequency)} disabled={busy}
            className="select-glass !w-auto !py-2 !text-xs">
            <option value="instant">Instant</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
          <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={handleCreate} disabled={busy}
            className="px-4 py-2 rounded-xl bg-accent text-white text-xs font-bold transition-all
                       disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_18px_rgba(139,92,246,0.4)] hover:shadow-[0_0_26px_rgba(139,92,246,0.7)]">
            {busy ? "Creating…" : "Create Alert"}
          </motion.button>
        </div>
      </div>

      {error && <p className="text-xs text-rose-300 mt-3 relative">{error}</p>}

      {activeAlerts.length > 0 && (
        <div className="mt-4 pt-4 border-t border-fg/[0.08] space-y-2 relative">
          <p className="text-[10px] font-semibold text-fg/40 uppercase tracking-[0.18em]">Active Alerts</p>
          <AnimatePresence initial={false}>
            {activeAlerts.map((a) => (
              <motion.div key={a.id}
                initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                className="flex items-center justify-between gap-3 px-3 py-2 rounded-xl bg-fg/[0.03] border border-fg/[0.08]">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase bg-violet-500/20 text-violet-200">{a.frequency}</span>
                  <span className="text-xs text-fg/50 truncate">
                    {a.destination || "email"}{a.filters?.location ? ` · ${String(a.filters.location)}` : ""}
                  </span>
                </div>
                <button onClick={() => handleDelete(a.id)} className="text-[11px] text-fg/40 hover:text-rose-300 transition-colors flex-shrink-0">Remove</button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
}
