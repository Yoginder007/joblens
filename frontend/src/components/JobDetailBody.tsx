"use client";

import type { RecentJob } from "@/lib/api";
import { daysAgo } from "@/lib/ui";
import CompanyAvatar from "./CompanyAvatar";

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
          <CompanyAvatar name={job.company} className="w-11 h-11 rounded-md" textClassName="text-sm" />
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-foreground leading-snug">{job.title}</h2>
            <p className="text-sm text-muted-foreground mt-1">
              <span className="font-medium text-foreground">{job.company}</span>
              {job.source && job.source !== job.company ? ` · via ${job.source}` : ""}
              {job.industry ? ` · ${job.industry}` : ""}
            </p>
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} aria-label="Close"
            className="w-9 h-9 rounded-md bg-muted text-muted-foreground hover:bg-muted/80 flex items-center justify-center shrink-0">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Meta chips */}
      <div className="flex flex-wrap items-center gap-2 mb-5">
        {job.location && (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-sm bg-muted text-xs text-muted-foreground font-medium">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            {job.location}
          </span>
        )}
        {job.work_model && (
          <span className="px-2.5 py-1 rounded-sm text-xs font-medium bg-secondary text-secondary-foreground uppercase tracking-wider">{job.work_model}</span>
        )}
        {job.job_type && (
          <span className="px-2.5 py-1 rounded-sm text-xs font-medium bg-muted text-muted-foreground uppercase tracking-wider">{job.job_type}</span>
        )}
        <span className="px-2.5 py-1 rounded-sm text-xs font-medium bg-muted text-muted-foreground">{job.required_experience_years}+ yrs</span>
        {fresh && (
          <span className="px-2.5 py-1 rounded-sm text-xs font-medium bg-muted text-muted-foreground">{fresh}</span>
        )}
      </div>

      {/* Skills */}
      {job.technical_skills && job.technical_skills.length > 0 && (
        <div className="mb-5">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">Skills</p>
          <div className="flex flex-wrap gap-1.5">
            {job.technical_skills.map((s) => (
              <span key={s} className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-secondary text-secondary-foreground">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Full description */}
      <div className="mb-6">
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">Description</p>
        <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">
          {job.description || "No description available for this posting."}
        </p>
      </div>

      {/* Apply */}
      {job.job_url && (
        <a href={job.job_url} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center justify-center gap-2 w-full py-3 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-all">
          Apply on {job.source || "site"}
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>
      )}
    </div>
  );
}
