"use client";

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { searchJobs, type RecentJob, type SearchV2Response, type SearchV2Filters } from "@/lib/api";
import AdvancedSearchPanel from "./AdvancedSearchPanel";
import JobDetailDrawer from "./JobDetailDrawer";
import { staggerItem } from "@/lib/motion";

const PAGE_SIZE = 10;

// Direction-aware page flip (custom = +1 forward / -1 back). Kept subtle: a
// gentle slide + slight tilt rather than a strong 3D rotation.
const flipVariants = {
  enter: (d: number) => ({ rotateY: d * 6, opacity: 0, x: d * 24 }),
  center: { rotateY: 0, opacity: 1, x: 0 },
  exit: (d: number) => ({ rotateY: d * -6, opacity: 0, x: d * -24 }),
};

export default function RecentJobsPanel() {
  const [data, setData] = useState<SearchV2Response | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<SearchV2Filters>({});
  const [page, setPage] = useState(0);
  const [dir, setDir] = useState(1); // 1 = forward, -1 = back (drives flip direction)
  const [selected, setSelected] = useState<RecentJob | null>(null);

  // Monotonic request id: only the latest fetch commits state.
  const reqIdRef = useRef(0);
  // Anchor for snapping the viewport back to the list top on page flips.
  const listTopRef = useRef<HTMLDivElement>(null);

  const fetchJobs = useCallback((currentFilters: SearchV2Filters) => {
    const reqId = ++reqIdRef.current;
    setLoading(true);
    searchJobs({ ...currentFilters, limit: 200 })
      .then((res) => {
        if (reqId !== reqIdRef.current) return;
        setData(res);
        setError(null);
      })
      .catch((e) => {
        if (reqId !== reqIdRef.current) return;
        setError(e.message);
      })
      .finally(() => {
        if (reqId === reqIdRef.current) setLoading(false);
      });
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchJobs(filters);
  }, [filters, fetchJobs]);

  const handleFiltersChange = useCallback((newFilters: SearchV2Filters) => {
    setFilters(newFilters);
    setPage(0); // new filter set → back to first page
  }, []);

  const jobs = useMemo(() => data?.jobs || [], [data]);
  const pageCount = Math.max(1, Math.ceil(jobs.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageJobs = useMemo(
    () => jobs.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE),
    [jobs, safePage]
  );

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
        <AdvancedSearchPanel onFiltersChange={handleFiltersChange} facets={data?.facets || null} totalJobs={data?.total ?? null} />
      </div>

      {error && (
        <div className="mb-8 px-4 py-3 rounded-2xl bg-rose-500/10 border border-rose-400/25 text-sm text-rose-300">{error}</div>
      )}

      {loading && !data && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="shimmer h-44 rounded-2xl border border-fg/[0.06]" />
          ))}
        </div>
      )}

      {!loading && jobs.length === 0 && !error && (
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

      {jobs.length > 0 && (
        <div>
          {/* Result header + page controls */}
          <div ref={listTopRef} className="flex items-center justify-between mb-4 scroll-mt-24">
            <p className="text-sm text-fg/60">
              Showing <span className="text-fg font-semibold">{safePage * PAGE_SIZE + 1}–{Math.min((safePage + 1) * PAGE_SIZE, jobs.length)}</span> of{" "}
              <span className="text-gradient font-bold">{jobs.length}</span> jobs
            </p>
            <PageControls page={safePage} pageCount={pageCount} onPrev={() => go(-1)} onNext={() => go(1)} disabled={loading} />
          </div>

          {/* Flip-paginated merged list (no source sections) */}
          <div className="relative" style={{ perspective: 1600 }}>
            <AnimatePresence mode="wait" custom={dir}>
              <motion.div
                key={safePage}
                custom={dir}
                variants={flipVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
                style={{ transformStyle: "preserve-3d" }}
                className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5"
              >
                {pageJobs.map((job) => <JobBrowseCard key={job.id} job={job} onOpen={setSelected} />)}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Bottom page controls + dots */}
          <div className="flex items-center justify-center gap-4 mt-8">
            <PageControls page={safePage} pageCount={pageCount} onPrev={() => go(-1)} onNext={() => go(1)} disabled={loading} />
          </div>
        </div>
      )}

      <JobDetailDrawer job={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function PageControls({
  page, pageCount, onPrev, onNext, disabled,
}: { page: number; pageCount: number; onPrev: () => void; onNext: () => void; disabled?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <motion.button
        whileTap={{ scale: 0.9 }} whileHover={{ scale: 1.05 }}
        onClick={onPrev} disabled={disabled || page === 0}
        className="w-9 h-9 rounded-xl glass glass-hover flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed"
        aria-label="Previous page"
      >
        <svg className="w-4 h-4 text-fg/70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
        </svg>
      </motion.button>
      <span className="text-xs text-fg/50 tabular-nums min-w-[54px] text-center">
        {page + 1} / {pageCount}
      </span>
      <motion.button
        whileTap={{ scale: 0.9 }} whileHover={{ scale: 1.05 }}
        onClick={onNext} disabled={disabled || page >= pageCount - 1}
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

function JobBrowseCard({ job, onOpen }: { job: RecentJob; onOpen: (job: RecentJob) => void }) {
  return (
    <motion.div
      variants={staggerItem}
      initial="hidden" animate="show"
      whileHover={{ y: -5 }}
      onClick={() => onOpen(job)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter") onOpen(job); }}
      className="group rounded-2xl glass glass-hover p-5 flex flex-col cursor-pointer
                 transition-shadow duration-300 hover:shadow-[0_18px_50px_-20px_rgba(139,92,246,0.45)]"
    >
      <div className="flex justify-between items-start mb-2">
        <h4 className="text-sm font-semibold text-fg group-hover:text-violet-500 dark:group-hover:text-violet-200 transition-colors line-clamp-2">{job.title}</h4>
        <div className="flex gap-1 shrink-0">
          {job.work_model && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-fg/8 text-fg/50">{job.work_model}</span>
          )}
        </div>
      </div>
      <p className="text-xs text-fg/50 mb-3">
        <span className="font-medium text-fg/70">{job.company}</span>
        {job.source && job.source !== job.company ? ` · via ${job.source}` : ""}
        {job.industry ? ` · ${job.industry}` : ""}
      </p>
      <p className="text-xs text-fg/45 line-clamp-2 mb-3">{job.description}</p>

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
          {job.technical_skills.slice(0, 5).map((skill) => (
            <span key={skill} className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-violet-500/12 text-violet-700 dark:text-violet-300 border border-violet-500/20">{skill}</span>
          ))}
          {job.technical_skills.length > 5 && (
            <span className="px-2 py-0.5 rounded-md text-[10px] text-fg/30">+{job.technical_skills.length - 5}</span>
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
