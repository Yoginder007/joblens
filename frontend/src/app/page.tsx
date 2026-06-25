"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import AnimatedNumber from "@/components/AnimatedNumber";
import MatchWizard from "@/components/MatchWizard";
import RotatingWord from "@/components/RotatingWord";
import ProcessingState from "@/components/ProcessingState";
import RecentJobsPanel from "@/components/RecentJobsPanel";
import ThemeToggle from "@/components/ThemeToggle";
import UserMenu from "@/components/UserMenu";
import { Button } from "@/components/ui/button";
import {
  createCandidate,
  uploadResume,
  streamResumeUntilReady,
  getEligibleJobs,
  getFilterOptions,
  searchJobs,
  type SearchFilters,
  type EligibleJobsResponse,
} from "@/lib/api";

import { setSession, patchSession, getToken } from "@/lib/session";
import { useAuth } from "@/lib/useAuth";
import { fadeUp, swap } from "@/lib/motion";

// Off the initial-paint critical path: the results dashboard (with its job-card
// grid + alerts) is only needed after the match runs, and the auth modal only
// when opened. Loading them as separate async chunks keeps the first render —
// the Browse tab — lean. Their chunks download during the processing wait.
const ResultsDashboard = dynamic(() => import("@/components/ResultsDashboard"), { ssr: false });
const AuthModal = dynamic(() => import("@/components/AuthModal"), { ssr: false });

type Phase = "configure" | "processing" | "results";
type Tab = "match" | "browse";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("browse");
  const [phase, setPhase] = useState<Phase>("configure");
  const [file, setFile] = useState<File | null>(null);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [processingStatus, setProcessingStatus] = useState("pending");
  const [results, setResults] = useState<EligibleJobsResponse | null>(null);
  const [resultsFilters, setResultsFilters] = useState<SearchFilters>({});
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [browseJobCount, setBrowseJobCount] = useState<number | null>(null);

  const [scrolled, setScrolled] = useState(false);

  const auth = useAuth();
  const { authed, acctEmail, acctName, authOpen, authMode, openAuth } = auth;

  const filtersRef = useRef<SearchFilters>({});

  useEffect(() => {
    searchJobs({ limit: 1, include_facets: false })
      .then((res) => setBrowseJobCount(res.total))
      .catch(() => setBrowseJobCount(0));
  }, []);

  // Warm the (cached) filter-option catalogue during idle time so the match
  // wizard's Preferences step and the browse advanced filters open instantly
  // rather than waiting on a fetch the moment the user gets there.
  useEffect(() => {
    const warm = () => void getFilterOptions().catch(() => {});
    const ric = (window as Window & {
      requestIdleCallback?: (cb: () => void) => number;
      cancelIdleCallback?: (id: number) => void;
    }).requestIdleCallback;
    if (ric) {
      const id = ric(warm);
      return () => (window as Window & { cancelIdleCallback?: (id: number) => void }).cancelIdleCallback?.(id);
    }
    const t = setTimeout(warm, 1200);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    // Mirror the signed-in account into the editable form fields.
    if (authed) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (acctEmail) setEmail(acctEmail);
      if (acctName) setFullName(acctName);
    }
  }, [authed, acctEmail, acctName]);

  const handleSignOut = () => {
    auth.signOut();
    setEmail("");
    setFullName("");
    handleReset();
  };

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const handleFiltersChange = useCallback((f: SearchFilters) => {
    filtersRef.current = f;
  }, []);

  const handleSubmit = async () => {
    if (!file || !email || !fullName) {
      setError("Please fill in all fields and upload a resume.");
      return;
    }
    setError(null);
    setIsSubmitting(true);

    try {
      let token = getToken();
      if (authed && token) {
      } else {
        const candidate = await createCandidate(email, fullName);
        token = candidate.access_token;
        setSession({ token, candidateId: candidate.id, email, fullName });
      }

      const resume = await uploadResume(token, file);

      setPhase("processing");
      setProcessingStatus("pending");

      const readyResume = await streamResumeUntilReady(token, resume.id, (status) => {
        setProcessingStatus(status);
      });
      patchSession({ resumeId: readyResume.id });

      setProcessingStatus("ready");

      // Fire the match query immediately and let it run *while* the brief
      // "Ready!" celebration plays, instead of waiting a fixed 800ms and only
      // then starting the fetch. Total time becomes max(fetch, ~0.45s) rather
      // than 0.8s + fetch — usually shaving the better part of a second off the
      // jump to results.
      const usedFilters = filtersRef.current;
      setResultsFilters(usedFilters);
      const [eligible] = await Promise.all([
        getEligibleJobs(token, readyResume.id, usedFilters),
        new Promise((r) => setTimeout(r, 450)),
      ]);
      setResults(eligible);
      setPhase("results");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setError(message);
      setPhase("configure");
      if (/log in/i.test(message)) openAuth("login");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setPhase("configure");
    setFile(null);
    setResults(null);
    setError(null);
    setProcessingStatus("pending");
  };

  const TABS: { id: Tab; label: string }[] = [
    { id: "browse", label: "Browse All" },
    { id: "match", label: "Match My Resume" },
  ];

  return (
    <MotionConfig reducedMotion="user">
      <div className="relative min-h-screen text-foreground bg-background font-sans selection:bg-muted selection:text-foreground">
        
        {/* ── Header ── */}
        <header className="sticky top-0 z-30">
          <div className={`transition-all duration-150 ${scrolled ? "bg-background/80 backdrop-blur-md border-b border-border shadow-sm" : "bg-transparent border-b border-transparent"}`}>
            <div className="max-w-6xl mx-auto px-6 py-3.5 flex items-center justify-between gap-4">
              <motion.div
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="flex items-center gap-3"
              >
                <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                  <svg className="w-4 h-4 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <circle cx="11" cy="11" r="3" strokeWidth={2} />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16.5 16.5L21 21" />
                  </svg>
                </div>
                <div>
                  <h1 className="text-sm font-semibold tracking-tight">JobLens</h1>
                </div>
              </motion.div>

              {/* Tab switcher */}
              <div className="relative flex items-center gap-1 bg-muted rounded-lg p-1">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => { setActiveTab(t.id); handleReset(); }}
                    className={`relative px-4 py-1.5 rounded-md text-sm font-medium transition-colors z-10 flex items-center gap-2 ${
                      activeTab === t.id ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {activeTab === t.id && (
                      <motion.div
                        layoutId="activeTab"
                        className="absolute inset-0 bg-background rounded-md shadow-sm border border-border"
                        transition={{ type: "spring", stiffness: 380, damping: 30 }}
                      />
                    )}
                    <span className="relative z-10">{t.label}</span>
                    {t.id === "browse" && browseJobCount ? (
                      <span className="relative z-10 px-1.5 py-0.5 rounded-sm text-[10px] font-mono bg-muted-foreground/10 tabular-nums">
                        {browseJobCount}
                      </span>
                    ) : null}
                  </button>
                ))}
              </div>

              <div className="flex items-center justify-end gap-3">
                <AnimatePresence>
                  {activeTab === "match" && phase === "results" && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.9 }}
                    >
                      <Button variant="outline" size="sm" onClick={handleReset}>
                        New Search
                      </Button>
                    </motion.div>
                  )}
                </AnimatePresence>
                <ThemeToggle />
                <UserMenu
                  authed={authed}
                  email={acctEmail}
                  fullName={acctName}
                  onLogin={() => openAuth("login")}
                  onSignup={() => openAuth("signup")}
                  onSignOut={handleSignOut}
                />
              </div>
            </div>
          </div>
        </header>

        {/* ── Auth modal ── */}
        <AuthModal
          open={authOpen}
          initialMode={authMode}
          onClose={auth.closeAuth}
          onAuthed={(user) => {
            auth.signIn(user);
            setEmail(user.email);
            setFullName(user.full_name);
          }}
        />

        {/* ── Error banner ── */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="relative z-20 max-w-6xl mx-auto px-6 mt-4"
            >
              <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive">
                <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span className="flex-1 font-medium">{error}</span>
                <button onClick={() => setError(null)} className="text-destructive/70 hover:text-destructive">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Main ── */}
        <main className="relative z-10 max-w-6xl mx-auto px-6 py-12">
          <AnimatePresence mode="wait">
            {/* ─── Browse ─── */}
            {activeTab === "browse" && (
              <motion.div key="browse" variants={swap} initial="hidden" animate="show" exit="exit">
                <Hero
                  title={
                    <>
                      <span>Discover </span>
                      <RotatingWord
                        className="text-primary"
                        words={["every open role.", "your next role.", "the perfect fit."]}
                      />
                    </>
                  }
                  subtitle="Browse all jobs posted in the last 2 months across every integrated board — no resume required."
                >
                  {browseJobCount !== null && browseJobCount > 0 && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.25, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                      className="mt-6 flex items-center justify-center gap-3 flex-wrap"
                    >
                      <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-background text-sm font-medium">
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-500 opacity-60" />
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                        </span>
                        <AnimatedNumber value={browseJobCount} />
                        <span className="text-muted-foreground font-normal">live roles</span>
                      </span>
                    </motion.div>
                  )}
                </Hero>
                <RecentJobsPanel />
              </motion.div>
            )}

            {/* ─── Match: configure ─── */}
            {activeTab === "match" && phase === "configure" && (
              <motion.div key="configure" variants={swap} initial="hidden" animate="show" exit="exit" className="max-w-2xl mx-auto">
                <Hero
                  title="Find your perfect role."
                  subtitle="Upload your resume and set your preferences. We'll match you with eligible roles and can keep alerting you as new ones land."
                />
                <motion.div variants={fadeUp} initial="hidden" animate="show">
                  <MatchWizard
                    authed={authed}
                    acctName={acctName}
                    acctEmail={acctEmail}
                    email={email}
                    setEmail={setEmail}
                    fullName={fullName}
                    setFullName={setFullName}
                    file={file}
                    setFile={setFile}
                    isSubmitting={isSubmitting}
                    onFiltersChange={handleFiltersChange}
                    onSubmit={handleSubmit}
                  />
                </motion.div>
              </motion.div>
            )}

            {/* ─── Match: processing ─── */}
            {activeTab === "match" && phase === "processing" && (
              <motion.div key="processing" variants={swap} initial="hidden" animate="show" exit="exit" className="max-w-lg mx-auto">
                <div className="p-8 border border-border rounded-xl bg-card shadow-sm">
                  <ProcessingState status={processingStatus} fileName={file?.name || "resume.pdf"} />
                </div>
              </motion.div>
            )}

            {/* ─── Match: results ─── */}
            {activeTab === "match" && phase === "results" && results && (
              <motion.div key="results" variants={swap} initial="hidden" animate="show" exit="exit">
                <ResultsDashboard data={results} filters={resultsFilters} />
              </motion.div>
            )}
          </AnimatePresence>
        </main>

        {/* ── Footer ── */}
        <footer className="relative z-10 border-t border-border mt-24">
          <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-sm text-muted-foreground font-medium">JobLens · Powered by FastAPI + Next.js</p>
            <div className="flex items-center gap-6">
              <a href={`${API_BASE}/api/docs`} target="_blank" rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors">API Docs</a>
              <a href={`${API_BASE}/api/health`} target="_blank" rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors">Health</a>
            </div>
          </div>
        </footer>
      </div>
    </MotionConfig>
  );
}

function Hero({ title, subtitle, children }: { title: React.ReactNode; subtitle: string; children?: React.ReactNode }) {
  return (
    <motion.div variants={fadeUp} initial="hidden" animate="show" className="text-center mb-12">
      <h2 className="text-4xl md:text-5xl font-semibold tracking-tight mb-4 leading-tight text-foreground">
        {title}
      </h2>
      <p className="text-base text-muted-foreground max-w-lg mx-auto leading-relaxed">{subtitle}</p>
      {children}
    </motion.div>
  );
}

