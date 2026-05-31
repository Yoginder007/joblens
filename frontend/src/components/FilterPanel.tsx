"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { getPortals, type Portal, type SearchFilters } from "@/lib/api";

interface FilterPanelProps {
  onFiltersChange: (filters: SearchFilters) => void;
  disabled?: boolean;
}

const WORK_MODELS = [
  { label: "Any", value: "" },
  { label: "Remote", value: "remote" },
  { label: "Hybrid", value: "hybrid" },
  { label: "On-site", value: "on-site" },
];
const JOB_TYPES = [
  { label: "Any type", value: "" },
  { label: "Full-time", value: "full-time" },
  { label: "Contract", value: "contract" },
  { label: "Internship", value: "internship" },
];
const DATE_POSTED = [
  { label: "Any time", value: "" },
  { label: "Last 24 hours", value: "1" },
  { label: "Last 3 days", value: "3" },
  { label: "Last week", value: "7" },
  { label: "Last 2 weeks", value: "14" },
  { label: "Last 30 days", value: "30" },
];

export default function FilterPanel({ onFiltersChange, disabled }: FilterPanelProps) {
  const [location, setLocation] = useState("");
  const [titleKeyword, setTitleKeyword] = useState("");
  const [expMin, setExpMin] = useState<number>(0);
  const [expMax, setExpMax] = useState<number>(20); // 20 = "Any"
  const [workModel, setWorkModel] = useState("");
  const [jobType, setJobType] = useState("");
  const [datePosted, setDatePosted] = useState("");
  const [portals, setPortals] = useState<Portal[]>([]);
  const [selectedPortals, setSelectedPortals] = useState<string[]>([]);

  const onFiltersChangeRef = useRef(onFiltersChange);
  useEffect(() => {
    onFiltersChangeRef.current = onFiltersChange;
  }, [onFiltersChange]);

  useEffect(() => {
    getPortals()
      .then((p) => {
        setPortals(p);
        setSelectedPortals(p.map((x) => x.company));
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    onFiltersChangeRef.current({
      location: location || undefined,
      title_keyword: titleKeyword || undefined,
      experience_min: expMin > 0 ? expMin : undefined,
      max_experience: expMax < 20 ? expMax : undefined,
      work_model: workModel || undefined,
      job_type: jobType || undefined,
      posted_within_days: datePosted ? Number(datePosted) : undefined,
      sources:
        selectedPortals.length > 0 && selectedPortals.length < portals.length
          ? selectedPortals
          : undefined,
    });
  }, [location, titleKeyword, expMin, expMax, workModel, jobType, datePosted, selectedPortals, portals.length]);

  const togglePortal = useCallback((company: string) => {
    setSelectedPortals((prev) =>
      prev.includes(company) ? prev.filter((c) => c !== company) : [...prev, company]
    );
  }, []);

  // Keep the two experience thumbs from crossing.
  const onMinChange = (v: number) => setExpMin(Math.min(v, expMax));
  const onMaxChange = (v: number) => setExpMax(Math.max(v, expMin));

  const allSelected = portals.length > 0 && selectedPortals.length === portals.length;
  const toggleAll = useCallback(() => {
    setSelectedPortals(allSelected ? [] : portals.map((p) => p.company));
  }, [allSelected, portals]);

  const resetAll = useCallback(() => {
    setLocation(""); setTitleKeyword(""); setExpMin(0); setExpMax(20);
    setWorkModel(""); setJobType(""); setDatePosted("");
    setSelectedPortals(portals.map((p) => p.company));
  }, [portals]);

  const labelCls = "block text-[10px] font-semibold text-fg/55 uppercase tracking-[0.18em] mb-2";

  return (
    <div className={`space-y-6 ${disabled ? "opacity-50 pointer-events-none" : ""}`}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold text-fg/40 uppercase tracking-[0.18em]">Refine results</span>
        <button type="button" onClick={resetAll} className="text-[10px] text-violet-600 dark:text-violet-300 hover:underline">
          Reset filters
        </button>
      </div>

      {/* Experience range (min–max) */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-[10px] font-semibold text-fg/55 uppercase tracking-[0.18em]">Experience Required</label>
          <span className="text-xs font-bold text-violet-600 dark:text-violet-300 tabular-nums">
            {expMin}{expMax >= 20 ? "+" : `–${expMax}`} yrs
          </span>
        </div>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-fg/45 w-8">Min</span>
            <input type="range" min={0} max={20} value={expMin}
              onChange={(e) => onMinChange(Number(e.target.value))}
              className="flex-1 h-1.5 bg-fg/10 rounded-full appearance-none cursor-pointer" />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-fg/45 w-8">Max</span>
            <input type="range" min={0} max={20} value={expMax}
              onChange={(e) => onMaxChange(Number(e.target.value))}
              className="flex-1 h-1.5 bg-fg/10 rounded-full appearance-none cursor-pointer" />
          </div>
        </div>
      </div>

      {/* Location */}
      <div>
        <label className={labelCls}>Location</label>
        <input type="text" value={location} onChange={(e) => setLocation(e.target.value)}
          placeholder="e.g. Bangalore, New York, Remote..." className="input-glass" />
      </div>

      {/* Work Model */}
      <div>
        <label className={labelCls}>Work Model</label>
        <div className="grid grid-cols-4 gap-2">
          {WORK_MODELS.map((m) => (
            <motion.button
              whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
              key={m.label} type="button" onClick={() => setWorkModel(m.value)}
              className={`px-2 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                workModel === m.value
                  ? "bg-accent text-white shadow-[0_0_18px_rgba(139,92,246,0.4)]"
                  : "bg-fg/[0.04] text-fg/60 hover:text-fg/90 border border-fg/8"
              }`}
            >
              {m.label}
            </motion.button>
          ))}
        </div>
      </div>

      {/* Job Type + Date Posted (real value selectors) */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Job Type</label>
          <select value={jobType} onChange={(e) => setJobType(e.target.value)} className="select-glass">
            {JOB_TYPES.map((t) => <option key={t.label} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <div>
          <label className={labelCls}>Date Posted</label>
          <select value={datePosted} onChange={(e) => setDatePosted(e.target.value)} className="select-glass">
            {DATE_POSTED.map((d) => <option key={d.label} value={d.value}>{d.label}</option>)}
          </select>
        </div>
      </div>

      {/* Title Keyword */}
      <div>
        <label className={labelCls}>Role / Title Keyword</label>
        <input type="text" value={titleKeyword} onChange={(e) => setTitleKeyword(e.target.value)}
          placeholder="e.g. SDE, Backend, Full Stack..." className="input-glass" />
      </div>

      {/* Career Portals */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-[10px] font-semibold text-fg/55 uppercase tracking-[0.18em]">Career Portals</label>
          {portals.length > 0 && (
            <button type="button" onClick={toggleAll}
              className="text-[10px] text-violet-600 dark:text-violet-300 hover:underline">
              {allSelected ? "Clear all" : "Select all"}
            </button>
          )}
        </div>
        {portals.length === 0 ? (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-fg/[0.02] border border-fg/5">
            <svg className="w-4 h-4 text-fg/20 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-xs text-fg/40">Loading portals...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {portals.map((portal) => {
              const on = selectedPortals.includes(portal.company);
              return (
                <motion.button
                  whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}
                  key={portal.company} type="button" onClick={() => togglePortal(portal.company)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl border transition-all ${
                    on ? "bg-fg/[0.06] border-violet-400/40 shadow-[0_0_16px_rgba(139,92,246,0.18)]"
                       : "bg-fg/[0.02] border-fg/10 hover:bg-fg/[0.04] opacity-70"
                  }`}
                >
                  <div className={`w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center transition-all ${on ? "border-violet-400 bg-accent" : "border-fg/25"}`}>
                    {on && (
                      <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>
                  <div className="flex-1 text-left min-w-0">
                    <p className="text-sm font-medium text-fg/85 truncate">{portal.company}</p>
                  </div>
                  <span className={`flex-shrink-0 px-2 py-0.5 rounded text-[9px] font-bold uppercase ${
                    portal.live
                      ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/25"
                      : "bg-fg/8 text-fg/50 border border-fg/10"
                  }`}>
                    {portal.live ? "Live" : "Curated"}
                  </span>
                </motion.button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
