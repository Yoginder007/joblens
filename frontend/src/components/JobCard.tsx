"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { EligibleJob } from "@/lib/api";
import ScoreRing from "./ScoreRing";
import CompanyAvatar from "./CompanyAvatar";

interface JobCardProps {
  job: EligibleJob;
  rank: number;
}

export default function JobCard({ job, rank }: JobCardProps) {
  const [expanded, setExpanded] = useState(false);

  const matchedSkills = job.matched_skills?.filter((s) => s.found_in_resume) || [];
  const missingSkills = job.matched_skills?.filter((s) => !s.found_in_resume) || [];
  const totalSkillsCount = job.matched_skills?.length || 0;

  return (
    <div
      className="group relative rounded-xl bg-card border border-border p-5 flex flex-col shadow-sm transition-all hover:shadow-md hover:border-primary/50"
    >
      {/* Rank badge */}
      <div className="absolute -top-2 -left-2 w-6 h-6 rounded-md bg-foreground flex items-center justify-center text-[10px] font-bold text-background shadow-sm">
        {rank}
      </div>

      <div className="flex items-start justify-between gap-4 mb-2">
        <div className="flex items-start gap-3 flex-1 min-w-0 cursor-pointer" onClick={() => setExpanded(!expanded)}>
          <CompanyAvatar name={job.company} className="w-10 h-10 rounded-md" textClassName="text-xs" />
          <div>
            <div className="flex justify-between items-start mb-1 gap-2">
              <h3 className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors line-clamp-2">
                {job.title}
              </h3>
              {job.work_model && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider bg-secondary text-secondary-foreground shrink-0">
                  {job.work_model}
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{job.company}</span>
              {job.source && job.source !== job.company ? ` · via ${job.source}` : ""}
              {job.industry ? ` · ${job.industry}` : ""}
            </p>
          </div>
        </div>
        <div onClick={() => setExpanded(!expanded)} className="flex-shrink-0 cursor-pointer">
          <ScoreRing value={job.match_score} />
        </div>
      </div>

      {/* Meta */}
      <div className="flex flex-wrap items-center gap-2 mb-3 mt-2">
        {job.location && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-muted text-xs text-muted-foreground font-medium">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            {job.location}
          </span>
        )}
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-muted text-xs text-muted-foreground font-medium">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {job.required_experience_years}+ yrs
        </span>
      </div>

      {/* Description preview */}
      {job.description && (
        <p className="text-xs text-muted-foreground leading-relaxed mb-4 line-clamp-2">
          {job.description}
        </p>
      )}

      {/* Skill alignment summary bar */}
      {totalSkillsCount > 0 && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
              Skill alignment
            </span>
            <span className="text-[10px] font-mono text-muted-foreground">
              {matchedSkills.length}/{totalSkillsCount} matched
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${(matchedSkills.length / totalSkillsCount) * 100}%` }}
              transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
              className="h-full rounded-full bg-foreground"
            />
          </div>
        </div>
      )}

      {/* Skill chips */}
      {totalSkillsCount > 0 ? (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {matchedSkills.slice(0, expanded ? matchedSkills.length : 5).map((s) => (
            <span key={s.skill}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-foreground text-background">
              <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              {s.skill}
            </span>
          ))}
          {missingSkills.slice(0, expanded ? missingSkills.length : 3).map((s) => (
            <span key={s.skill}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-secondary text-secondary-foreground">
              <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              {s.skill}
            </span>
          ))}
          {!expanded && matchedSkills.length + missingSkills.length > 8 && (
            <span onClick={() => setExpanded(true)}
              className="px-2 py-0.5 rounded-md text-[10px] text-primary cursor-pointer hover:underline">
              +{matchedSkills.length + missingSkills.length - 8} more
            </span>
          )}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground italic mb-2">No specific skills listed for this role.</p>
      )}

      {/* Expandable detail */}
      {totalSkillsCount > 0 && (
        <button onClick={() => setExpanded(!expanded)}
          className="self-start text-[10px] text-primary hover:underline mb-2 mt-1 font-medium">
          {expanded ? "Hide details" : "Show breakdown"}
        </button>
      )}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }} className="overflow-hidden"
          >
            <div className="mb-3 p-3 rounded-md bg-muted/50 border border-border space-y-2">
              {job.description && (
                <p className="text-[11px] text-muted-foreground leading-relaxed border-b border-border pb-2 mb-2">
                  {job.description}
                </p>
              )}
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Semantic relevance</span>
                <span className="text-foreground font-mono font-medium">{job.semantic_similarity.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Skill match</span>
                <span className="text-foreground font-mono font-medium">{job.skill_match_percentage.toFixed(0)}%</span>
              </div>
              {missingSkills.length > 0 && (
                <p className="text-[10px] text-muted-foreground leading-relaxed pt-1 mt-1 border-t border-border">
                  <strong className="text-foreground">To improve your match:</strong> add{" "}
                  {missingSkills.slice(0, 3).map((s) => s.skill).join(", ")}
                  {missingSkills.length > 3 ? "…" : ""} if you have that experience.
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 mt-auto border-t border-border">
        <p className="text-[10px] text-muted-foreground font-mono truncate max-w-[160px]">ID: {job.job_id.slice(0, 12)}</p>
        {job.job_url ? (
          <a href={job.job_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors">
            Apply
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        ) : (
          <span className="text-xs text-muted-foreground">No link</span>
        )}
      </div>
    </div>
  );
}
