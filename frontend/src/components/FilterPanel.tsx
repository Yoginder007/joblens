"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { getPortals, getFilterOptions, type FilterOptions, type Portal, type SearchFilters } from "@/lib/api";
import Dropdown, { type DropdownOption } from "./Dropdown";

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
const JOB_TYPES: DropdownOption[] = [
  { value: "", label: "Any type" },
  { value: "full-time", label: "Full-time" },
  { value: "contract", label: "Contract" },
  { value: "internship", label: "Internship" },
];
const DATE_POSTED: DropdownOption[] = [
  { value: "", label: "Any time" },
  { value: "1", label: "Last 24 hours" },
  { value: "3", label: "Last 3 days" },
  { value: "7", label: "Last week" },
  { value: "14", label: "Last 2 weeks" },
  { value: "30", label: "Last 30 days" },
  { value: "60", label: "Last 2 months" },
  { value: "90", label: "Last 3 months" },
];

export default function FilterPanel({ onFiltersChange, disabled }: FilterPanelProps) {
  const [location, setLocation] = useState("");
  const [titleKeyword, setTitleKeyword] = useState("");
  const [expMin, setExpMin] = useState<number>(0);
  const [expMax, setExpMax] = useState<number>(20); // 20 = "Any"
  const [workModel, setWorkModel] = useState("");
  const [jobType, setJobType] = useState("");
  const [datePosted, setDatePosted] = useState("");
  const [matchMode, setMatchMode] = useState<"semantic" | "direct">("semantic");
  const [portals, setPortals] = useState<Portal[]>([]);
  const [selectedPortals, setSelectedPortals] = useState<string[]>([]);
  const [opts, setOpts] = useState<FilterOptions | null>(null);

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
    getFilterOptions().then(setOpts).catch(console.error);
  }, []);

  // Searchable option lists, sourced from live data (countries first for location).
  const locationOptions = useMemo<DropdownOption[]>(() => {
    const seen = new Set<string>();
    const out: DropdownOption[] = [];
    for (const c of opts?.countries || []) {
      if (seen.has(c.toLowerCase())) continue;
      seen.add(c.toLowerCase());
      out.push({ value: c, label: `${c} — all`, hint: "country" });
    }
    for (const l of opts?.locations || []) {
      if (seen.has(l.toLowerCase())) continue;
      seen.add(l.toLowerCase());
      out.push({ value: l, label: l });
    }
    return out;
  }, [opts]);
  const titleOptions = useMemo<DropdownOption[]>(
    () => (opts?.titles || []).map((t) => ({ value: t, label: t })),
    [opts]
  );

  useEffect(() => {
    onFiltersChangeRef.current({
      location: location || undefined,
      title_keyword: titleKeyword || undefined,
      experience_min: expMin > 0 ? expMin : undefined,
      max_experience: expMax < 20 ? expMax : undefined,
      work_model: workModel || undefined,
      job_type: jobType || undefined,
      posted_within_days: datePosted ? Number(datePosted) : undefined,
      match_mode: matchMode,
      sources:
        selectedPortals.length > 0 && selectedPortals.length < portals.length
          ? selectedPortals
          : undefined,
    });
  }, [location, titleKeyword, expMin, expMax, workModel, jobType, datePosted, matchMode, selectedPortals, portals.length]);

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
    setWorkModel(""); setJobType(""); setDatePosted(""); setMatchMode("semantic");
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

      {/* Match mode — Smart (AI) vs Direct (filter-driven) */}
      <div>
        <label className={labelCls}>Match Mode</label>
        <div className="grid grid-cols-2 gap-2">
          {([
            { v: "semantic", label: "Smart Match", hint: "AI relevance + skills" },
            { v: "direct", label: "Direct Filter", hint: "your filters + skills only" },
          ] as const).map((m) => (
            <motion.button
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              key={m.v} type="button" onClick={() => setMatchMode(m.v)}
              className={`flex flex-col items-start px-3 py-2 rounded-xl border text-left transition-all ${
                matchMode === m.v
                  ? "bg-accent text-white border-transparent shadow-[0_0_18px_rgba(139,92,246,0.4)]"
                  : "bg-fg/[0.04] text-fg/70 border-fg/10 hover:text-fg"
              }`}
            >
              <span className="text-xs font-bold">{m.label}</span>
              <span className={`text-[10px] ${matchMode === m.v ? "text-white/80" : "text-fg/45"}`}>{m.hint}</span>
            </motion.button>
          ))}
        </div>
        <p className="text-[10px] text-fg/40 mt-2 leading-relaxed">
          {matchMode === "direct"
            ? "Direct Filter ranks by how many of a job's listed skills you have — best when you've set location/experience and want clean, predictable results."
            : "Smart Match blends semantic relevance with skill overlap for a holistic score."}
        </p>
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
        <Dropdown value={location} onChange={setLocation} options={locationOptions} searchable
          disabled={disabled} placeholder="Type or pick a location…" ariaLabel="Location" />
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

      {/* Job Type + Date Posted (animated dropdowns) */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Job Type</label>
          <Dropdown value={jobType} onChange={setJobType} options={JOB_TYPES} disabled={disabled} ariaLabel="Job type" />
        </div>
        <div>
          <label className={labelCls}>Date Posted</label>
          <Dropdown value={datePosted} onChange={setDatePosted} options={DATE_POSTED} disabled={disabled} ariaLabel="Date posted" />
        </div>
      </div>

      {/* Role / Title Keyword */}
      <div>
        <label className={labelCls}>Role / Title Keyword</label>
        <Dropdown value={titleKeyword} onChange={setTitleKeyword} options={titleOptions} searchable
          disabled={disabled} placeholder="Type or pick a role…" ariaLabel="Role or title" />
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
