"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { AnimatePresence, motion, useMotionValue, useSpring } from "framer-motion";
import { searchJobs, type FacetCounts, type RecentJob, type SearchV2Filters } from "@/lib/api";
import AdvancedSearchPanel from "./AdvancedSearchPanel";
import JobDetailDrawer from "./JobDetailDrawer";
import JobDetailBody from "./JobDetailBody";
import { staggerItem } from "@/lib/motion";
import { companyGradient, companyInitials, daysAgo } from "@/lib/ui";
import { useMediaQuery } from "@/lib/useMediaQuery";

const PAGE_SIZE = 10;

// Direction-aware page flip (custom = +1 forward / -1 back). Kept subtle: a
// gentle slide + slight tilt rather than a strong 3D rotation. The exit is
// much shorter than the enter — with mode="wait" the exit is dead air, and
// the server fetch already adds latency before the flip can start.
const flipVariants = {
  enter: (d: number) => ({
    rotateY: d * 6, opacity: 0, x: d * 24,
    transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] as const },
  }),
  center: {
    rotateY: 0, opacity: 1, x: 0,
    transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] as const },
  },
  exit: (d: number) => ({
    rotateY: d * -6, opacity: 0, x: d * -24,
    transition: { duration: 0.13, ease: "easeIn" as const },
  }),
};

export default function RecentJobsPanel() {
  // Server-side pagination: each page is its own query (limit/offset), so the
  // catalogue can grow without a client-side cap. `view` only advances when
  // fresh data lands — the flip animation always plays over real content.
  const [view, setView] = useState<{ page: number; jobs: RecentJob[] }>({ page: 0, jobs: [] });
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState<FacetCounts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<SearchV2Filters>({});
  const [page, setPage] = useState(0);
  const [dir, setDir] = useState(1); // 1 = forward, -1 = back (drives flip direction)
  const [selected, setSelected] = useState<RecentJob | null>(null);

  // Desktop (xl+) renders a LinkedIn-style split view: list left, sticky
  // detail pane right. Below xl, tapping a card opens the slide-over drawer.
  const isDesktop = useMediaQuery("(min-width: 1280px)");

  // Monotonic request id: only the latest fetch commits state.
  const reqIdRef = useRef(0);
  // Anchor for snapping the viewport back to the list top on page flips.
  const listTopRef = useRef<HTMLDivElement>(null);
  // Per-filter-set page cache + next-page prefetch make flips instant: the
  // network round-trip happens before the user asks for the page.
  const cacheRef = useRef<Map<number, RecentJob[]>>(new Map());

  const prefetch = useCallback((currentFilters: SearchV2Filters, pageN: number) => {
    if (cacheRef.current.has(pageN)) return;
    cacheRef.current.set(pageN, []); // reserve so we don't double-fetch
    searchJobs({ ...currentFilters, limit: PAGE_SIZE, offset: pageN * PAGE_SIZE, include_facets: false })
      .then((res) => cacheRef.current.set(pageN, res.jobs))
      .catch(() => cacheRef.current.delete(pageN));
  }, []);

  const fetchPage = useCallback((currentFilters: SearchV2Filters, pageN: number) => {
    const cached = cacheRef.current.get(pageN);
    if (cached && cached.length > 0) {
      // Instant flip from cache; warm the next page in the background.
      reqIdRef.current++; // invalidate any in-flight fetch
      setView({ page: pageN, jobs: cached });
      setLoading(false);
      setError(null);
      prefetch(currentFilters, pageN + 1);
      return;
    }
    const reqId = ++reqIdRef.current;
    setLoading(true);
    searchJobs({
      ...currentFilters,
      limit: PAGE_SIZE,
      offset: pageN * PAGE_SIZE,
      // Facets depend on filters, not the page — only pay for them on page 0.
      include_facets: pageN === 0,
    })
      .then((res) => {
        if (reqId !== reqIdRef.current) return;
        cacheRef.current.set(pageN, res.jobs);
        setView({ page: pageN, jobs: res.jobs });
        setTotal(res.total);
        if (res.facets) setFacets(res.facets);
        setError(null);
        if ((pageN + 1) * PAGE_SIZE < res.total) prefetch(currentFilters, pageN + 1);
      })
      .catch((e) => {
        if (reqId !== reqIdRef.current) return;
        setError(e.message);
      })
      .finally(() => {
        if (reqId === reqIdRef.current) setLoading(false);
      });
  }, [prefetch]);

  useEffect(() => {
    fetchPage(filters, page);
  }, [filters, page, fetchPage]);

  const handleFiltersChange = useCallback((newFilters: SearchV2Filters) => {
    cacheRef.current.clear(); // cache is per filter set
    setFilters(newFilters);
    setPage(0); // new filter set → back to first page
  }, []);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const safePage = view.page;
  const pageJobs = view.jobs;

  // Desktop: keep something selected so the detail pane is never empty.
  // Mobile: selection drives the drawer, so it must stay user-initiated.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelected((cur) => {
      if (!isDesktop) return null;
      return cur && pageJobs.some((j) => j.id === cur.id) ? cur : pageJobs[0] ?? null;
    });
  }, [isDesktop, pageJobs]);

  // Desktop: ↑/↓ moves the selection through the visible page.
  useEffect(() => {
    if (!isDesktop) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      const tag = (document.activeElement?.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      e.preventDefault();
      setSelected((cur) => {
        const idx = pageJobs.findIndex((j) => j.id === cur?.id);
        const next = e.key === "ArrowDown"
          ? Math.min(idx + 1, pageJobs.length - 1)
          : Math.max(idx - 1, 0);
        return pageJobs[next] ?? cur;
      });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isDesktop, pageJobs]);

  // Reset the detail pane's internal scroll when the selected job changes —
  // otherwise a new job appears mid-scroll and looks broken.
  const paneRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    paneRef.current?.scrollTo({ top: 0 });
  }, [selected?.id]);

  const go = (delta: number) => {
    setDir(delta);
    setPage((p) => Math.min(Math.max(p + delta, 0), pageCount - 1));
    // Bottom pagination flips happen out of view — bring the list back.
    listTopRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div>
      <div className="mb-8">
        {/* NOTE: do NOT disable the filters while loading — this is a debounced
            live search, and disabling mid-interaction blocks adding a 2nd
            location/company (pointer-events-none on an open dropdown). */}
        <AdvancedSearchPanel onFiltersChange={handleFiltersChange} facets={facets} totalJobs={total || (loading ? null : 0)} />
      </div>

      {error && (
        <div className="mb-8 px-4 py-3 rounded-2xl bg-rose-500/10 border border-rose-400/25 text-sm text-rose-300">{error}</div>
      )}

      {loading && pageJobs.length === 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="shimmer h-44 rounded-2xl border border-fg/[0.06]" />
          ))}
        </div>
      )}

      {!loading && total === 0 && !error && (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-2xl bg-fg/5 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-fg/20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
          </div>
          <p className="text-sm text-fg/40 mb-2">No jobs match your filters</p>
          <p className="text-xs text-fg/20">Try adjusting your search criteria or clearing filters.</p>
        </div>
      )}

      {pageJobs.length > 0 && (
        <div>
          {/* Result header + page controls */}
          <div ref={listTopRef} className="flex items-center justify-between mb-4 scroll-mt-24">
            <p className="text-sm text-fg/60">
              Showing <span className="text-fg font-semibold">{safePage * PAGE_SIZE + 1}–{Math.min((safePage + 1) * PAGE_SIZE, total)}</span> of{" "}
              <span className="text-gradient font-bold">{total}</span> jobs
              {isDesktop && <span className="text-fg/30 text-xs ml-3 hidden xl:inline">↑↓ to browse</span>}
            </p>
            <PageControls page={safePage} pageCount={pageCount} onPrev={() => go(-1)} onNext={() => go(1)} loading={loading} />
          </div>

          {/* xl+: split view (list + sticky detail pane). Below xl: card grid + drawer. */}
          <div className="xl:grid xl:grid-cols-[420px_minmax(0,1fr)] xl:gap-6 xl:items-start">
            <div>
              {/* Flip-paginated merged list (no source sections). Dim slightly
                  while the next page is in flight — the flip plays when it lands. */}
              <div className={`relative transition-opacity duration-200 ${loading ? "opacity-60" : ""}`}
                style={{ perspective: 1600 }}>
                <AnimatePresence mode="wait" custom={dir}>
                  <motion.div
                    key={safePage}
                    custom={dir}
                    variants={flipVariants}
                    initial="enter"
                    animate="center"
                    exit="exit"
                    style={{ transformStyle: "preserve-3d" }}
                    className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-1 gap-5 xl:gap-3"
                  >
                    {pageJobs.map((job) => (
                      <JobBrowseCard
                        key={job.id}
                        job={job}
                        active={isDesktop && selected?.id === job.id}
                        compact={isDesktop}
                        onOpen={setSelected}
                      />
                    ))}
                  </motion.div>
                </AnimatePresence>
              </div>

              {/* Bottom page controls */}
              <div className="flex items-center justify-center gap-4 mt-8">
                <PageControls page={safePage} pageCount={pageCount} onPrev={() => go(-1)} onNext={() => go(1)} loading={loading} />
              </div>
            </div>

            {/* Sticky detail pane (desktop only). popLayout crossfades the
                outgoing job with the incoming one — no empty-pane flash. */}
            <div ref={paneRef} className="hidden xl:block sticky top-24 max-h-[calc(100vh-7.5rem)] overflow-y-auto rounded-3xl glass-strong">
              <AnimatePresence mode="popLayout" initial={false}>
                {selected ? (
                  <motion.div
                    key={selected.id}
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10, transition: { duration: 0.15 } }}
                    transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <JobDetailBody job={selected} />
                  </motion.div>
                ) : (
                  <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="flex flex-col items-center justify-center py-24 text-center px-8">
                    <div className="w-14 h-14 rounded-2xl bg-fg/5 flex items-center justify-center mb-4">
                      <svg className="w-7 h-7 text-fg/25" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    </div>
                    <p className="text-sm text-fg/40">Select a job to see the full posting here.</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      )}

      {/* Mobile / tablet: slide-over drawer */}
      {!isDesktop && <JobDetailDrawer job={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function PageControls({
  page, pageCount, onPrev, onNext, loading,
}: { page: number; pageCount: number; onPrev: () => void; onNext: () => void; loading?: boolean }) {
  // NOTE: never disable on `loading` — clicks must always respond (the
  // request-id guard makes rapid paging safe). Only the bounds disable.
  return (
    <div className="flex items-center gap-2">
      <motion.button
        whileTap={{ scale: 0.9 }} whileHover={{ scale: 1.05 }}
        onClick={onPrev} disabled={page === 0}
        className="w-9 h-9 rounded-xl glass glass-hover flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed"
        aria-label="Previous page"
      >
        <svg className="w-4 h-4 text-fg/70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
        </svg>
      </motion.button>
      <span className="relative text-xs text-fg/50 tabular-nums min-w-[54px] text-center">
        {page + 1} / {pageCount}
        {loading && (
          <svg className="animate-spin w-3 h-3 text-violet-400 absolute -right-4 top-1/2 -translate-y-1/2" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
      </span>
      <motion.button
        whileTap={{ scale: 0.9 }} whileHover={{ scale: 1.05 }}
        onClick={onNext} disabled={page >= pageCount - 1}
        className="w-9 h-9 rounded-xl glass glass-hover flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed"
        aria-label="Next page"
      >
        <svg className="w-4 h-4 text-fg/70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
        </svg>
      </motion.button>
    </div>
  );
}

function JobBrowseCard({
  job, onOpen, active = false, compact = false,
}: { job: RecentJob; onOpen: (job: RecentJob) => void; active?: boolean; compact?: boolean }) {
  // Subtle pointer-tracked 3D tilt (springs back on leave).
  const rx = useMotionValue(0);
  const ry = useMotionValue(0);
  const srx = useSpring(rx, { stiffness: 220, damping: 18 });
  const sry = useSpring(ry, { stiffness: 220, damping: 18 });

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    ry.set(((e.clientX - r.left) / r.width - 0.5) * 5);
    rx.set(-((e.clientY - r.top) / r.height - 0.5) * 5);
  };
  const onLeave = () => { rx.set(0); ry.set(0); };

  const fresh = daysAgo(job.posted_date || job.scraped_at);

  return (
    <motion.div
      variants={staggerItem}
      initial="hidden" animate="show"
      whileHover={{ y: -4 }}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{ rotateX: srx, rotateY: sry, transformPerspective: 900 }}
      onClick={() => onOpen(job)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter") onOpen(job); }}
      className={`group rounded-2xl glass glass-hover p-5 flex flex-col cursor-pointer
                  transition-shadow duration-300 hover:shadow-[0_18px_50px_-20px_rgba(139,92,246,0.45)]
                  ${active ? "ring-1 ring-violet-400/60 !border-violet-400/40 !bg-fg/[0.05]" : ""}`}
    >
      <div className="flex items-start gap-3 mb-2">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center text-[11px] font-bold text-white shrink-0 mt-0.5"
          style={{ backgroundImage: companyGradient(job.company) }}
        >
          {companyInitials(job.company)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex justify-between items-start gap-2">
            <h4 className="text-sm font-semibold text-fg group-hover:text-violet-500 dark:group-hover:text-violet-200 transition-colors line-clamp-2">{job.title}</h4>
            <div className="flex items-center gap-1.5 shrink-0">
              {fresh && <span className="text-[9px] text-fg/35 whitespace-nowrap">{fresh}</span>}
              {job.work_model && (
                <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-fg/8 text-fg/50">{job.work_model}</span>
              )}
            </div>
          </div>
          <p className="text-xs text-fg/50 mt-0.5">
            <span className="font-medium text-fg/70">{job.company}</span>
            {job.source && job.source !== job.company ? ` · via ${job.source}` : ""}
            {job.industry ? ` · ${job.industry}` : ""}
          </p>
        </div>
      </div>

      {!compact && <p className="text-xs text-fg/45 line-clamp-2 mb-3">{job.description}</p>}

      <div className="flex flex-wrap items-center gap-2 mb-3">
        {job.location && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-fg/[0.06] text-xs text-fg/55">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            {job.location}
          </span>
        )}
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-fg/[0.06] text-xs text-fg/55">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {job.required_experience_years}+ yrs
        </span>
      </div>

      {job.technical_skills && job.technical_skills.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {job.technical_skills.slice(0, compact ? 4 : 5).map((skill) => (
            <span key={skill} className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-violet-500/12 text-violet-700 dark:text-violet-300 border border-violet-500/20">{skill}</span>
          ))}
          {job.technical_skills.length > (compact ? 4 : 5) && (
            <span className="px-2 py-0.5 rounded-md text-[10px] text-fg/30">+{job.technical_skills.length - (compact ? 4 : 5)}</span>
          )}
        </div>
      )}

      <div className="flex items-center justify-between pt-2 mt-auto border-t border-fg/[0.06]">
        <p className="text-[10px] text-fg/30 font-mono truncate max-w-[160px]">{job.source_id}</p>
        {job.job_url ? (
          <a href={job.job_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-accent text-white text-xs font-semibold hover:shadow-[0_0_16px_rgba(139,92,246,0.5)] transition-all">
            View
            <svg className="w-3 h-3 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
              fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        ) : (
          <span className="text-[10px] text-fg/30">No link</span>
        )}
      </div>
    </motion.div>
  );
}
