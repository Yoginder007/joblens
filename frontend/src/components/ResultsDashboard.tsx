"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import JobCard from "./JobCard";
import JobAlerts from "./JobAlerts";
import AnimatedNumber from "./AnimatedNumber";
import type { EligibleJob, EligibleJobsResponse, SearchFilters } from "@/lib/api";
import { staggerContainer, staggerItem } from "@/lib/motion";

interface ResultsDashboardProps {
  data: EligibleJobsResponse;
  filters?: SearchFilters;
}

export default function ResultsDashboard({ data, filters = {} }: ResultsDashboardProps) {
  const [activeSource, setActiveSource] = useState<string | null>(null);

  const grouped = useMemo(() => {
    const groups: Record<string, EligibleJob[]> = {};
    for (const job of data.eligible_jobs) {
      let source = "Other";
      if (job.job_url) {
        try {
          source = new URL(job.job_url).hostname.replace("www.", "");
        } catch {
          source = "Other";
        }
      }
      if (!groups[source]) groups[source] = [];
      groups[source].push(job);
    }
    return groups;
  }, [data.eligible_jobs]);

  const sources = Object.keys(grouped);
  const visibleSource = activeSource || sources[0] || null;

  const avgScore = data.eligible_jobs.length > 0
    ? data.eligible_jobs.reduce((s, j) => s + j.match_score, 0) / data.eligible_jobs.length
    : 0;

  const topMissingSkills = useMemo(() => {
    const count: Record<string, number> = {};
    for (const job of data.eligible_jobs) {
      for (const s of job.matched_skills || []) {
        if (!s.found_in_resume) count[s.skill] = (count[s.skill] || 0) + 1;
      }
    }
    return Object.entries(count).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([s]) => s);
  }, [data.eligible_jobs]);

  return (
    <div>
      <JobAlerts resumeId={data.resume_id} filters={filters} />

      {/* Stats */}
      <motion.div variants={staggerContainer(0.1)} initial="hidden" animate="show" className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <motion.div variants={staggerItem} className="rounded-2xl glass p-5">
          <p className="text-[10px] text-muted-foreground uppercase tracking-[0.18em] font-semibold">Total Matches</p>
          <p className="text-3xl font-bold text-fg mt-1"><AnimatedNumber value={data.total_eligible} /></p>
          <p className="text-xs text-fg/30 mt-1">across {sources.length} source{sources.length !== 1 ? "s" : ""}</p>
        </motion.div>
        <motion.div variants={staggerItem} className="rounded-2xl glass p-5">
          <p className="text-[10px] text-muted-foreground uppercase tracking-[0.18em] font-semibold">Avg Score</p>
          <p className="text-3xl font-bold text-fg mt-1"><AnimatedNumber value={avgScore} decimals={1} suffix="%" /></p>
          <p className="text-xs text-fg/30 mt-1">{data.candidate_experience_years}y experience matched</p>
        </motion.div>
        <motion.div variants={staggerItem} className="rounded-2xl glass p-5">
          <p className="text-[10px] text-muted-foreground uppercase tracking-[0.18em] font-semibold">Most Missing Skills</p>
          <div className="flex flex-wrap gap-1 mt-2">
            {topMissingSkills.length > 0
              ? topMissingSkills.slice(0, 4).map((s) => (
                  <span key={s} className="px-2 py-0.5 rounded text-[10px] bg-muted text-muted-foreground border border-border">{s}</span>
                ))
              : <span className="text-xs text-fg/30 italic">None</span>}
          </div>
        </motion.div>
      </motion.div>

      {/* Source tabs */}
      {sources.length > 0 && (
        <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2">
          {sources.map((source) => (
            <button key={source} onClick={() => setActiveSource(source)}
              className={`relative flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-colors z-10 ${
                visibleSource === source ? "text-foreground" : "text-fg/40 hover:text-fg/70"
              }`}
            >
              {visibleSource === source && (
                <motion.div layoutId="activeSourceTab" className="absolute inset-0 bg-secondary border border-border rounded-xl -z-10"
                  transition={{ type: "spring", stiffness: 380, damping: 30 }} />
              )}
              <span className="w-5 h-5 rounded-md bg-fg/8 flex items-center justify-center text-[10px] font-bold">{grouped[source].length}</span>
              {source}
            </button>
          ))}
        </div>
      )}

      {/* Cards */}
      {visibleSource && grouped[visibleSource] && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-fg/60">Matches from <span className="text-gradient font-bold">{visibleSource}</span></h2>
            <span className="text-xs text-fg/30">{grouped[visibleSource].length} job{grouped[visibleSource].length !== 1 ? "s" : ""}</span>
          </div>
          <motion.div
            key={visibleSource}
            variants={staggerContainer(0.06)}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5"
          >
            {grouped[visibleSource].map((job, i) => (
              <motion.div key={job.job_id} variants={staggerItem}>
                <JobCard job={job} rank={i + 1} />
              </motion.div>
            ))}
          </motion.div>
        </div>
      )}

      {data.eligible_jobs.length === 0 && (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-2xl bg-fg/5 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-fg/20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <p className="text-sm text-fg/40">No eligible jobs found. Try adjusting your filters.</p>
        </div>
      )}
    </div>
  );
}
