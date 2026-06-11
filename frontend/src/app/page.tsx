"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import AnimatedNumber from "@/components/AnimatedNumber";
import MatchWizard from "@/components/MatchWizard";
import RotatingWord from "@/components/RotatingWord";
import ProcessingState from "@/components/ProcessingState";
import ResultsDashboard from "@/components/ResultsDashboard";
import RecentJobsPanel from "@/components/RecentJobsPanel";
import ThemeToggle from "@/components/ThemeToggle";
import AuroraBackground from "@/components/AuroraBackground";
import AuthModal from "@/components/AuthModal";
import UserMenu from "@/components/UserMenu";
import {
  createCandidate,
  uploadResume,
  pollResumeUntilReady,
  getEligibleJobs,
  searchJobs,
  type SearchFilters,
  type EligibleJobsResponse,
} from "@/lib/api";
import { setSession, patchSession, getSession, clearSession, getToken } from "@/lib/session";
import { fadeUp, swap } from "@/lib/motion";

type Phase = "configure" | "processing" | "results";
type Tab = "match" | "browse";

// Backend base URL — same source the API client uses, so footer links resolve
// to the deployed API in production and localhost in dev.
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

  // Auth state (hydrated from the persisted session on mount).
  const [authed, setAuthed] = useState(false);
  const [acctEmail, setAcctEmail] = useState<string | undefined>();
  const [acctName, setAcctName] = useState<string | undefined>();
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");

  const filtersRef = useRef<SearchFilters>({});

  useEffect(() => {
    // Exact catalogue size from the search total (uncapped, one cheap query).
    searchJobs({ limit: 1, include_facets: false })
      .then((res) => setBrowseJobCount(res.total))
      .catch(() => setBrowseJobCount(0));
  }, []);

  // Hydrate auth state from the stored session (client-only, one-shot).
  useEffect(() => {
    const s = getSession();
    if (s?.account) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAuthed(true);
      setAcctEmail(s.email);
      setAcctName(s.fullName);
      if (s.email) setEmail(s.email);
      if (s.fullName) setFullName(s.fullName);
    }
  }, []);

  const openAuth = (mode: "login" | "signup") => { setAuthMode(mode); setAuthOpen(true); };

  const handleSignOut = () => {
    clearSession();
    setAuthed(false);
    setAcctEmail(undefined);
    setAcctName(undefined);
    setEmail("");
    setFullName("");
    handleReset();
  };

  // Strengthen the header background once the page scrolls so content can't
  // bleed through the translucent bar.
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
      // Logged-in users reuse their account session; guests get a one-time token.
      let token = getToken();
      if (authed && token) {
        // keep existing account session
      } else {
        const candidate = await createCandidate(email, fullName);
        token = candidate.access_token;
        setSession({ token, candidateId: candidate.id, email, fullName });
      }

      const resume = await uploadResume(token, file);

      setPhase("processing");
      setProcessingStatus("pending");

      const readyResume = await pollResumeUntilReady(token, resume.id, (status) => {
        setProcessingStatus(status);
      });
      patchSession({ resumeId: readyResume.id });

      setProcessingStatus("ready");
      await new Promise((r) => setTimeout(r, 800));

      const usedFilters = filtersRef.current;
      setResultsFilters(usedFilters);
      const eligible = await getEligibleJobs(token, readyResume.id, usedFilters);
      setResults(eligible);
      setPhase("results");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setError(message);
      setPhase("configure");
      // Guest flow hit a password-protected account → route them to login.
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
      <div className="relative min-h-screen text-fg">
        {/* ── Aurora background (cursor-parallax) ── */}
        <AuroraBackground />

        {/* ── Header ── */}
        <header className="sticky top-0 z-30">
          <div className={`border-x-0 border-t-0 transition-all duration-150 ${scrolled ? "header-solid" : "glass"}`}>
            <div className="max-w-6xl mx-auto px-6 py-3.5 flex items-center justify-between gap-4">
              <motion.div
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="flex items-center gap-3"
              >
                <div className="w-9 h-9 rounded-2xl bg-accent flex items-center justify-center shadow-[0_0_24px_rgba(139,92,246,0.5)]">
                  {/* JobLens mark: a lens/aperture focusing on the right role */}
                  <svg className="w-5 h-5 on-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <motion.circle
                      cx="11" cy="11" r="7" strokeWidth={2}
                      animate={{ rotate: 360 }} style={{ transformOrigin: "11px 11px" }}
                      transition={{ duration: 14, repeat: Infinity, ease: "linear" }}
                      strokeDasharray="3 3"
                    />
                    <circle cx="11" cy="11" r="3" strokeWidth={2} />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16.5 16.5L21 21" />
                  </svg>
                </div>
                <div>
                  <h1 className="text-sm font-extrabold tracking-tight text-fg">JobLens</h1>
                  <p className="text-[10px] text-fg/35 uppercase tracking-[0.2em]">Resume → Roles</p>
                </div>
              </motion.div>

              {/* Tab switcher */}
              <div className="relative flex items-center gap-1 glass rounded-2xl p-1">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => { setActiveTab(t.id); handleReset(); }}
                    className={`relative px-4 py-2 rounded-xl text-xs font-semibold transition-colors z-10 flex items-center gap-2 ${
                      activeTab === t.id ? "on-accent" : "text-fg/45 hover:text-fg/80"
                    }`}
                  >
                    {activeTab === t.id && (
                      <motion.div
                        layoutId="activeTab"
                        className="absolute inset-0 bg-accent rounded-xl shadow-[0_0_20px_rgba(139,92,246,0.45)]"
                        transition={{ type: "spring", stiffness: 380, damping: 30 }}
                      />
                    )}
                    <span className="relative z-10">{t.label}</span>
                    {t.id === "browse" && browseJobCount ? (
                      <span className="relative z-10 px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-fg/15 tabular-nums">
                        {browseJobCount}
                      </span>
                    ) : null}
                  </button>
                ))}
              </div>

              <div className="flex items-center justify-end gap-2">
                <AnimatePresence>
                  {activeTab === "match" && phase === "results" && (
                    <motion.button
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.9 }}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      onClick={handleReset}
                      className="px-4 py-2 rounded-xl glass glass-hover text-xs font-semibold text-fg/70"
                    >
                      New Search
                    </motion.button>
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
          onClose={() => setAuthOpen(false)}
          onAuthed={(user) => {
            setAuthed(true);
            setAcctEmail(user.email);
            setAcctName(user.full_name);
            setEmail(user.email);
            setFullName(user.full_name);
            setAuthOpen(false);
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
              <div className="flex items-center gap-3 px-4 py-3 rounded-2xl bg-rose-500/10 border border-rose-500/25 text-sm text-rose-300 backdrop-blur-xl">
                <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span className="flex-1">{error}</span>
                <button onClick={() => setError(null)} className="text-rose-300/60 hover:text-rose-200">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Main ── */}
        <main className="relative z-10 max-w-6xl mx-auto px-6 py-10">
          <AnimatePresence mode="wait">
            {/* ─── Browse ─── */}
            {activeTab === "browse" && (
              <motion.div key="browse" variants={swap} initial="hidden" animate="show" exit="exit">
                <Hero
                  title={
                    <>
                      <span className="text-gradient-animate">Discover </span>
                      <RotatingWord
                        className="text-gradient-animate"
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
                      className="mt-5 flex items-center justify-center gap-2 flex-wrap"
                    >
                      <span className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full glass text-xs font-semibold text-fg/70">
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
                        </span>
                        <AnimatedNumber value={browseJobCount} />
                        <span className="text-fg/45 font-medium">live roles</span>
                      </span>
                      <span className="px-3.5 py-1.5 rounded-full glass text-xs font-medium text-fg/50">
                        Real apply links
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
                <div className="glass-strong rounded-3xl">
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
        <footer className="relative z-10 border-t border-fg/[0.06] mt-16">
          <div className="max-w-6xl mx-auto px-6 py-6 flex flex-col md:flex-row items-center justify-between gap-3">
            <p className="text-xs text-fg/25">JobLens · Powered by FastAPI + Next.js</p>
            <div className="flex items-center gap-4">
              <a href={`${API_BASE}/api/docs`} target="_blank" rel="noopener noreferrer"
                className="text-xs text-violet-500 dark:text-violet-300/50 hover:text-violet-200 transition-colors">API Docs</a>
              <a href={`${API_BASE}/api/health`} target="_blank" rel="noopener noreferrer"
                className="text-xs text-violet-500 dark:text-violet-300/50 hover:text-violet-200 transition-colors">Health</a>
            </div>
          </div>
        </footer>
      </div>
    </MotionConfig>
  );
}

function Hero({ title, subtitle, children }: { title: React.ReactNode; subtitle: string; children?: React.ReactNode }) {
  return (
    <motion.div variants={fadeUp} initial="hidden" animate="show" className="text-center mb-10">
      <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4 leading-[1.1]">
        {typeof title === "string" ? <span className="text-gradient-animate">{title}</span> : title}
      </h2>
      <p className="text-sm text-fg/45 max-w-lg mx-auto leading-relaxed">{subtitle}</p>
      {children}
    </motion.div>
  );
}
