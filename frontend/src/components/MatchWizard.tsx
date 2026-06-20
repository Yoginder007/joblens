"use client";

import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ResumeUploader from "./ResumeUploader";
import FilterPanel from "./FilterPanel";
import { Button } from "@/components/ui/button";
import type { SearchFilters } from "@/lib/api";

const EASE = [0.16, 1, 0.3, 1] as const;

interface MatchWizardProps {
  authed: boolean;
  acctName?: string;
  acctEmail?: string;
  email: string;
  setEmail: (v: string) => void;
  fullName: string;
  setFullName: (v: string) => void;
  file: File | null;
  setFile: (f: File | null) => void;
  isSubmitting: boolean;
  onFiltersChange: (f: SearchFilters) => void;
  onSubmit: () => void;
}

const STEPS = [
  { label: "Profile", hint: "You + your résumé" },
  { label: "Preferences", hint: "Filters & match mode" },
  { label: "Launch", hint: "Review & go" },
];

/**
 * Three-step match flow. All steps stay mounted (visibility toggled) so
 * FilterPanel state survives back/forward navigation; only the active step is
 * displayed and animated in.
 */
export default function MatchWizard({
  authed, acctName, acctEmail,
  email, setEmail, fullName, setFullName,
  file, setFile, isSubmitting, onFiltersChange, onSubmit,
}: MatchWizardProps) {
  const [step, setStep] = useState(0);
  // FilterPanel is the heavy subtree (portal grid + dropdowns + data fetches).
  // Mounting it lazily keeps the tab-switch render cheap; once mounted it
  // stays mounted so selections survive back/forward navigation.
  const [prefsMounted, setPrefsMounted] = useState(false);
  const goStep = (i: number) => {
    if (i >= 1) setPrefsMounted(true);
    setStep(i);
  };
  // Mirror of the latest filters, for the step-3 summary chips.
  const [summary, setSummary] = useState<SearchFilters>({});

  const handleFilters = useCallback((f: SearchFilters) => {
    setSummary(f);
    onFiltersChange(f);
  }, [onFiltersChange]);

  const profileOk = !!file && (authed || (email.trim().length > 3 && fullName.trim().length > 0));

  const summaryChips: string[] = [
    summary.match_mode === "direct" ? "Direct Filter" : "Smart Match",
    ...(summary.location ? [summary.location] : []),
    ...(summary.title_keyword ? [summary.title_keyword] : []),
    ...(summary.experience_min !== undefined || summary.max_experience !== undefined
      ? [`${summary.experience_min ?? 0}–${summary.max_experience ?? "any"} yrs`]
      : []),
    ...(summary.work_model ? [summary.work_model] : []),
    ...(summary.job_type ? [summary.job_type] : []),
    ...(summary.posted_within_days ? [`last ${summary.posted_within_days}d`] : []),
    ...(summary.sources?.length ? [`${summary.sources.length} portals`] : []),
  ];

  return (
    <div className="bg-card border border-border shadow-sm rounded-xl p-8">
      {/* ── Progress rail ── */}
      <div className="flex items-center mb-8">
        {STEPS.map((s, i) => {
          const done = i < step;
          const current = i === step;
          const reachable = i <= step || (i === step + 1 && profileOk);
          return (
            <div key={s.label} className={`flex items-center ${i > 0 ? "flex-1" : ""}`}>
              {i > 0 && (
                <div className="flex-1 h-px mx-3 bg-muted relative overflow-hidden rounded-full">
                  <motion.div
                    className="absolute inset-y-0 left-0 bg-primary"
                    initial={false}
                    animate={{ width: done || current ? "100%" : "0%" }}
                    transition={{ duration: 0.45, ease: EASE }}
                  />
                </div>
              )}
              <button
                type="button"
                onClick={() => reachable && goStep(i)}
                disabled={!reachable}
                className={`flex items-center gap-2.5 group ${reachable ? "cursor-pointer" : "cursor-not-allowed"}`}
              >
                <span className={`relative w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold transition-all duration-300 ${
                  current
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : done
                      ? "bg-foreground text-background border border-foreground"
                      : "bg-muted text-muted-foreground border border-border"
                }`}>
                  {/* Crossfade (no mode="wait") so the badge never shows an
                      empty frame mid-swap; absolute stacking keeps it stable. */}
                  <AnimatePresence initial={false}>
                    {done ? (
                      <motion.svg key="check" initial={{ scale: 0, rotate: -40 }} animate={{ scale: 1, rotate: 0 }} exit={{ scale: 0 }}
                        transition={{ type: "spring", stiffness: 500, damping: 26 }}
                        className="absolute w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </motion.svg>
                    ) : (
                      <motion.span key="num" className="absolute inset-0 flex items-center justify-center"
                        initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.6, opacity: 0 }}>
                        {i + 1}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </span>
                <span className="hidden sm:block text-left">
                  <span className={`block text-xs font-bold ${current ? "text-foreground" : "text-muted-foreground"}`}>{s.label}</span>
                  <span className="block text-[10px] text-muted-foreground">{s.hint}</span>
                </span>
              </button>
            </div>
          );
        })}
      </div>

      {/* ── Step 1: Profile ── */}
      <WizardStep active={step === 0}>
        {authed ? (
          <div className="flex items-center gap-3 mb-6 px-4 py-3 rounded-xl bg-muted/50 border border-border">
            <div className="w-9 h-9 rounded-lg bg-foreground flex items-center justify-center text-[11px] font-bold text-background shrink-0">
              {(acctName || acctEmail || "?").slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground truncate">{acctName || "Signed in"}</p>
              <p className="text-xs text-muted-foreground truncate">{acctEmail}</p>
            </div>
            <span className="ml-auto text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md bg-secondary text-secondary-foreground">
              Signed in
            </span>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            <div>
              <FieldLabel>Full Name</FieldLabel>
              <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)}
                placeholder="Yoginder Kumar" className="input-glass" />
            </div>
            <div>
              <FieldLabel>Email</FieldLabel>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com" className="input-glass" />
            </div>
          </div>
        )}

        <FieldLabel>Resume</FieldLabel>
        <ResumeUploader onFileSelected={setFile} disabled={isSubmitting} />

        <div className="flex justify-end mt-8">
          <Button disabled={!profileOk} onClick={() => goStep(1)}>
            Set Preferences
            <svg className="w-3.5 h-3.5 ml-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Button>
        </div>
        {!profileOk && (
          <p className="text-right text-[11px] text-muted-foreground mt-2">
            {file ? "Add your name and email to continue." : "Upload your résumé (PDF) to continue."}
          </p>
        )}
      </WizardStep>

      {/* ── Step 2: Preferences ── */}
      <WizardStep active={step === 1}>
        {prefsMounted && <FilterPanel onFiltersChange={handleFilters} disabled={isSubmitting} />}
        <div className="flex justify-between mt-8">
          <Button variant="outline" onClick={() => goStep(0)}>
            <svg className="w-3.5 h-3.5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 17l-5-5m0 0l5-5m-5 5h12" />
            </svg>
            Back
          </Button>
          <Button onClick={() => goStep(2)}>
            Review &amp; Launch
            <svg className="w-3.5 h-3.5 ml-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Button>
        </div>
      </WizardStep>

      {/* ── Step 3: Review & launch ── */}
      <WizardStep active={step === 2}>
        <div className="space-y-4 mb-8">
          <SummaryRow label="Candidate">
            <span className="text-sm text-foreground font-medium">
              {authed ? (acctName || acctEmail) : `${fullName} · ${email}`}
            </span>
          </SummaryRow>
          <SummaryRow label="Résumé">
            <span className="inline-flex items-center gap-2 text-sm text-foreground font-medium">
              <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {file?.name || "—"}
            </span>
          </SummaryRow>
          <SummaryRow label="Search setup">
            <div className="flex flex-wrap gap-1.5">
              {summaryChips.map((c) => (
                <span key={c} className="px-2.5 py-1 rounded-md text-xs font-medium bg-secondary text-secondary-foreground capitalize">
                  {c}
                </span>
              ))}
              {summaryChips.length <= 1 && (
                <span className="text-xs text-muted-foreground italic self-center">No extra filters — searching everything.</span>
              )}
            </div>
          </SummaryRow>
        </div>

        <div className="flex items-center justify-between gap-4">
          <Button variant="outline" onClick={() => goStep(1)}>
            <svg className="w-3.5 h-3.5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 17l-5-5m0 0l5-5m-5 5h12" />
            </svg>
            Back
          </Button>
          <Button
            onClick={onSubmit}
            disabled={isSubmitting || !profileOk}
            className="flex-1 font-semibold"
          >
            {isSubmitting ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Processing…
              </span>
            ) : "Find Matching Jobs"}
          </Button>
        </div>
      </WizardStep>
    </div>
  );
}

/* Steps stay mounted; the active one fades/slides in, inactive ones hide. */
function WizardStep({ active, children }: { active: boolean; children: React.ReactNode }) {
  return (
    <motion.div
      initial={false}
      animate={active ? { opacity: 1, x: 0, filter: "blur(0px)" } : { opacity: 0, x: 28, filter: "blur(4px)" }}
      transition={{ duration: 0.4, ease: EASE }}
      style={{ display: active ? "block" : "none" }}
    >
      {children}
    </motion.div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">
      {children}
    </label>
  );
}

function SummaryRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-4 px-4 py-3 rounded-lg bg-muted/30 border border-border">
      <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest w-24 shrink-0 mt-1">{label}</span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}
