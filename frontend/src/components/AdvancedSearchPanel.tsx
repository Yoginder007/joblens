"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { getFilterOptions, type FilterOptions, type SearchV2Filters, type FacetCounts } from "@/lib/api";
import Dropdown, { type DropdownOption } from "./Dropdown";
import MultiDropdown from "./MultiDropdown";

interface Props {
  onFiltersChange: (filters: SearchV2Filters) => void;
  disabled?: boolean;
  facets: FacetCounts | null;
  totalJobs: number | null;
}

const WORK_MODEL_LABEL: Record<string, string> = {
  remote: "Remote", hybrid: "Hybrid", "on-site": "On-site",
};
const JOB_TYPE_LABEL: Record<string, string> = {
  "full-time": "Full-time", contract: "Contract", internship: "Internship",
};
const DATE_OPTIONS: DropdownOption[] = [
  { value: "", label: "Any time" },
  { value: "1", label: "Last 24 hours" },
  { value: "3", label: "Last 3 days" },
  { value: "7", label: "Last week" },
  { value: "14", label: "Last 2 weeks" },
  { value: "30", label: "Last 30 days" },
  { value: "60", label: "Last 2 months" },
  { value: "90", label: "Last 3 months" },
  { value: "120", label: "Last 4 months" },
  { value: "180", label: "Last 6 months" },
  { value: "365", label: "Last year" },
];
const DATE_FACET_KEY: Record<string, string> = {
  "1": "24h", "3": "3d", "7": "7d", "14": "14d", "30": "30d",
};

// One-click experience presets → experience_min/max. Lets users grab relevant
// jobs without touching detailed filters.
const EXPERIENCE_PRESETS: Array<{ id: string; label: string; min?: number; max?: number }> = [
  { id: "fresher", label: "Fresher", min: 0, max: 0 },
  { id: "0-1", label: "0–1 yr", min: 0, max: 1 },
  { id: "1-3", label: "1–3 yrs", min: 1, max: 3 },
  { id: "3-5", label: "3–5 yrs", min: 3, max: 5 },
  { id: "5plus", label: "5+ yrs", min: 5 },
];

export default function AdvancedSearchPanel({ onFiltersChange, disabled, facets, totalJobs }: Props) {
  const [q, setQ] = useState("");
  const [locations, setLocations] = useState<string[]>([]);
  const [workModel, setWorkModel] = useState("");
  const [industry, setIndustry] = useState("");
  const [jobType, setJobType] = useState("");
  const [postedWithin, setPostedWithin] = useState("");
  const [companies, setCompanies] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState<"date" | "relevance" | "salary">("date");
  const [preset, setPreset] = useState<string>(""); // active experience preset id
  const [opts, setOpts] = useState<FilterOptions | null>(null);

  useEffect(() => {
    getFilterOptions().then(setOpts).catch(console.error);
  }, []);

  const activePreset = EXPERIENCE_PRESETS.find((p) => p.id === preset);

  useEffect(() => {
    const timeout = setTimeout(() => {
      // Location is the primary filter; everything else is optional and only
      // narrows further when set. Empty values are omitted entirely.
      onFiltersChange({
        q: q || undefined,
        location: locations.length ? locations.join(",") : undefined,
        work_model: workModel || undefined,
        industry: industry || undefined,
        job_type: jobType || undefined,
        posted_within_days: postedWithin ? parseInt(postedWithin, 10) : undefined,
        companies: companies.length ? companies : undefined,
        experience_min: activePreset?.min,
        experience_max: activePreset?.max,
        sort_by: sortBy,
      });
    }, 400);
    return () => clearTimeout(timeout);
  }, [q, locations, workModel, industry, jobType, postedWithin, companies, sortBy, activePreset, onFiltersChange]);

  const titleOptions = useMemo<DropdownOption[]>(
    () => (opts?.titles || []).map((t) => ({ value: t, label: t })),
    [opts]
  );
  // Countries first (pick a whole country), then specific cities from the data.
  // Dedupe by lowercased value so a country (e.g. "Canada") and an identically
  // named data location don't produce duplicate options / colliding React keys.
  const locationOptions = useMemo<DropdownOption[]>(() => {
    const seen = new Set<string>();
    const out: DropdownOption[] = [];
    for (const c of opts?.countries || []) {
      const key = c.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ value: c, label: `${c} — all`, hint: "country" });
    }
    for (const l of opts?.locations || []) {
      const key = l.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ value: l, label: l });
    }
    return out;
  }, [opts]);
  const companyOptions = useMemo<DropdownOption[]>(
    () => (opts?.companies || []).map((c) => ({ value: c, label: c })),
    [opts]
  );
  const workModelOptions = useMemo<DropdownOption[]>(() => {
    const vals = opts?.work_models?.length ? opts.work_models : ["remote", "hybrid", "on-site"];
    return [
      { value: "", label: "Any model" },
      ...vals.map((v) => ({ value: v, label: WORK_MODEL_LABEL[v] ?? v, hint: facets?.work_model?.[v] ?? "" })),
    ];
  }, [opts, facets]);
  const jobTypeOptions = useMemo<DropdownOption[]>(() => {
    const vals = opts?.job_types?.length ? opts.job_types : ["full-time", "contract", "internship"];
    return [
      { value: "", label: "Any type" },
      ...vals.map((v) => ({ value: v, label: JOB_TYPE_LABEL[v] ?? v, hint: facets?.job_types?.[v] ?? "" })),
    ];
  }, [opts, facets]);
  const industryOptions = useMemo<DropdownOption[]>(
    () => [
      { value: "", label: "All industries" },
      ...(opts?.industries || []).map((i) => ({ value: i, label: i, hint: facets?.industries?.[i] ?? "" })),
    ],
    [opts, facets]
  );
  const dateOptions = useMemo<DropdownOption[]>(
    () => DATE_OPTIONS.map((d) => ({
      ...d,
      hint: d.value && DATE_FACET_KEY[d.value] ? facets?.posted_within?.[DATE_FACET_KEY[d.value]] ?? "" : "",
    })),
    [facets]
  );

  const sorts: Array<{ id: "date" | "relevance" | "salary"; label: string }> = [
    { id: "date", label: "Date" },
    { id: "relevance", label: "Relevance" },
    { id: "salary", label: "Salary" },
  ];
  const labelCls = "block text-[10px] font-semibold text-fg/55 uppercase tracking-[0.18em] mb-2";

  const clearAll = () => {
    setQ(""); setLocations([]); setWorkModel(""); setIndustry(""); setJobType("");
    setPostedWithin(""); setCompanies([]); setSortBy("date"); setPreset("");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="glass-strong rounded-2xl p-6"
    >
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-sm font-bold text-fg uppercase tracking-wider flex items-center gap-2">
          <svg className="w-4 h-4 text-violet-500 dark:text-violet-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          Advanced Filters
        </h3>
        {totalJobs !== null && (
          <span className="text-xs text-fg/50">
            <span className="text-gradient font-bold">{totalJobs}</span> jobs found
          </span>
        )}
      </div>

      {/* Location — the primary filter, spans full width */}
      <div className="mb-5">
        <label className={labelCls}>
          Location <span className="text-violet-500 dark:text-violet-300 normal-case tracking-normal">· add as many as you like</span>
        </label>
        <MultiDropdown
          values={locations} onChange={setLocations} options={locationOptions} searchable
          disabled={disabled} placeholder="e.g. India, Bangalore, Remote…" ariaLabel="Locations"
        />
      </div>

      {/* Companies — multi-select */}
      <div className="mb-5">
        <label className={labelCls}>
          Companies <span className="text-fg/30 normal-case tracking-normal">· optional, pick one or more</span>
        </label>
        <MultiDropdown
          values={companies} onChange={setCompanies} options={companyOptions} searchable
          disabled={disabled} placeholder="e.g. Microsoft, Google, Amazon…" ariaLabel="Companies"
        />
      </div>

      {/* Quick experience presets — one click, no detail needed */}
      <div className="mb-5">
        <label className={labelCls}>Quick filters</label>
        <div className="flex flex-wrap gap-2">
          {EXPERIENCE_PRESETS.map((p) => {
            const on = preset === p.id;
            return (
              <motion.button
                key={p.id} type="button" disabled={disabled}
                whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                onClick={() => setPreset(on ? "" : p.id)}
                className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all ${
                  on
                    ? "bg-accent text-white shadow-[0_0_18px_rgba(139,92,246,0.4)]"
                    : "bg-fg/[0.05] text-fg/70 hover:text-fg border border-fg/10"
                }`}
              >
                {p.label}
              </motion.button>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="lg:col-span-2">
          <label className={labelCls}>Search Keywords <span className="text-fg/30 normal-case tracking-normal">· optional</span></label>
          <Dropdown value={q} onChange={setQ} options={titleOptions} searchable disabled={disabled}
            placeholder="Type or pick a role…" ariaLabel="Search keywords" />
        </div>
        <div>
          <label className={labelCls}>Work Model</label>
          <Dropdown value={workModel} onChange={setWorkModel} options={workModelOptions} disabled={disabled} ariaLabel="Work model" />
        </div>
        <div>
          <label className={labelCls}>Job Type</label>
          <Dropdown value={jobType} onChange={setJobType} options={jobTypeOptions} disabled={disabled} ariaLabel="Job type" />
        </div>
        <div>
          <label className={labelCls}>Industry</label>
          <Dropdown value={industry} onChange={setIndustry} options={industryOptions} searchable disabled={disabled} placeholder="All industries" ariaLabel="Industry" />
        </div>
        <div>
          <label className={labelCls}>Date Posted</label>
          <Dropdown value={postedWithin} onChange={setPostedWithin} options={dateOptions} disabled={disabled} ariaLabel="Date posted" />
        </div>
      </div>

      <div className="mt-6 pt-6 border-t border-fg/[0.08] flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="text-[10px] font-semibold text-fg/55 uppercase tracking-[0.18em]">Sort By</span>
          <div className="flex bg-fg/[0.04] p-1 rounded-lg">
            {sorts.map((s) => (
              <button key={s.id} onClick={() => setSortBy(s.id)}
                className={`relative px-3 py-1 text-xs rounded-md transition-all z-10 ${sortBy === s.id ? "on-accent" : "text-fg/45 hover:text-fg/80"}`}>
                {sortBy === s.id && (
                  <motion.div layoutId="sortPill" className="absolute inset-0 bg-accent rounded-md -z-10"
                    transition={{ type: "spring", stiffness: 380, damping: 30 }} />
                )}
                {s.label}
              </button>
            ))}
          </div>
        </div>
        <button onClick={clearAll} className="text-xs text-fg/45 hover:text-fg transition-colors">
          Clear Filters
        </button>
      </div>
    </motion.div>
  );
}
