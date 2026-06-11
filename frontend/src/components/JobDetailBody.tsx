"use client";

import type { RecentJob } from "@/lib/api";
import { companyGradient, companyInitials, daysAgo } from "@/lib/ui";

interface JobDetailBodyProps {
  job: RecentJob;
  /** Rendered as a close button when provided (drawer mode). */
  onClose?: () => void;
}

/**
 * A job's full detail (header, meta, skills, description, apply CTA).
 * Shared by the mobile slide-over drawer and the desktop split-view pane.
 */
export default function JobDetailBody({ job, onClose }: JobDetailBodyProps) {
  const fresh = daysAgo(job.posted_date || job.scraped_at);

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-start gap-3 min-w-0">
          <div
            className="w-11 h-11 rounded-xl flex items-center justify-center text-[13px] font-bold text-white shrink-0 shadow-lg"
            style={{ backgroundImage: companyGradient(job.company) }}
          >
            {companyInitials(job.company)}
          </div>
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-fg leading-snug">{job.title}</h2>
            <p className="text-sm text-fg/60 mt-1">
              <span className="font-medium text-fg/80">{job.company}</span>
              {job.source && job.source !== job.company ? ` · via ${job.source}` : ""}
              {job.industry ? ` · ${job.industry}` : ""}
            </p>
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} aria-label="Close"
            className="w-9 h-9 rounded-xl glass glass-hover flex items-center justify-center shrink-0">
            <svg className="w-4 h-4 text-fg/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Meta chips */}
      <div className="flex flex-wrap items-center gap-2 mb-5">
        {job.location && (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-fg/[0.06] text-xs text-fg/70">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            {job.location}
          </span>
        )}
        {job.work_model && (
          <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-violet-500/15 text-violet-700 dark:text-violet-300 capitalize">{job.work_model}</span>
        )}
        {job.job_type && (
          <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-fg/[0.06] text-fg/70 capitalize">{job.job_type}</span>
        )}
        <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-fg/[0.06] text-fg/70">{job.required_experience_years}+ yrs</span>
        {fresh && (
          <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">{fresh}</span>
        )}
      </div>

      {/* Skills */}
      {job.technical_skills && job.technical_skills.length > 0 && (
        <div className="mb-5">
          <p className="text-[10px] font-semibold text-fg/55 uppercase tracking-[0.18em] mb-2">Skills</p>
          <div className="flex flex-wrap gap-1.5">
            {job.technical_skills.map((s) => (
              <span key={s} className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-violet-500/12 text-violet-700 dark:text-violet-300 border border-violet-500/20">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Full description */}
      <div className="mb-6">
        <p className="text-[10px] font-semibold text-fg/55 uppercase tracking-[0.18em] mb-2">Description</p>
        <p className="text-sm text-fg/70 leading-relaxed whitespace-pre-line">
          {job.description || "No description available for this posting."}
        </p>
      </div>

      {/* Apply */}
      {job.job_url && (
        <a href={job.job_url} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center justify-center gap-2 w-full py-3 rounded-2xl bg-accent on-accent text-sm font-bold hover:shadow-[0_10px_40px_-8px_rgba(139,92,246,0.7)] transition-all">
          Apply on {job.source || "site"}
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>
      )}
    </div>
  );
}
