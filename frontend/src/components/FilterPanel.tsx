"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  getPortals,
  searchJobs,
  type FacetCounts,
  type Portal,
  type SearchFilters,
} from "@/lib/api";
import Dropdown, { type DropdownOption } from "./Dropdown";
import FilterPills, { type Pill } from "./FilterPills";
import { useFilterOptions } from "@/lib/useFilterOptions";

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
  { value: "part-time", label: "Part-time" },
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
const DATE_FACET_KEY: Record<string, string> = {
  "1": "24h", "3": "3d", "7": "7d", "14": "14d", "30": "30d",
};

// Amazon-style single-choice experience levels (radio semantics) instead of
// the old min/max slider pair — one tap covers the common cases.
const EXPERIENCE_LEVELS: Array<{ id: string; label: string; min?: number; max?: number }> = [
  { id: "", label: "Any" },
  { id: "fresher", label: "Fresher", min: 0, max: 0 },
  { id: "0-1", label: "0–1 yr", min: 0, max: 1 },
  { id: "1-3", label: "1–3 yrs", min: 1, max: 3 },
  { id: "3-5", label: "3–5 yrs", min: 3, max: 5 },
  { id: "5-8", label: "5–8 yrs", min: 5, max: 8 },
  { id: "8plus", label: "8+ yrs", min: 8 },
];

const PORTAL_GROUPS: Array<{ id: Portal["group"]; label: string }> = [
  { id: "india", label: "Indian companies" },
  { id: "global", label: "Global MNCs" },
  { id: "aggregator", label: "Job boards & aggregators" },
];

/**
 * Match-flow filters, Amazon-jobs style: facet groups with live result counts,
 * removable active-filter pills, and a live "N jobs match" preview that updates
 * as filters change (debounced public search with facets).
 */
export default function FilterPanel({ onFiltersChange, disabled }: FilterPanelProps) {
  const [location, setLocation] = useState("");
  const [titleKeyword, setTitleKeyword] = useState("");
  const [expLevel, setExpLevel] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const [workModel, setWorkModel] = useState("");
  const [jobType, setJobType] = useState("");
  const [datePosted, setDatePosted] = useState("");
  const [matchMode, setMatchMode] = useState<"semantic" | "direct">("semantic");
  const [portals, setPortals] = useState<Portal[]>([]);
  const [selectedPortals, setSelectedPortals] = useState<string[]>([]);

  // Live preview of how many jobs the current filters match (+ facet counts
  // for the option chips). This is what makes the panel adaptive.
  const [facets, setFacets] = useState<FacetCounts | null>(null);
  const [previewTotal, setPreviewTotal] = useState<number | null>(null);

  // Shared with the browse filter UI (countries-first location dedupe etc.).
  const { opts, locationOptions, titleOptions } = useFilterOptions();

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

  const activeLevel = EXPERIENCE_LEVELS.find((l) => l.id === expLevel);
  const sourcesSubset =
    selectedPortals.length > 0 && selectedPortals.length < portals.length
      ? selectedPortals
      : undefined;

  useEffect(() => {
    onFiltersChangeRef.current({
      location: location || undefined,
      title_keyword: titleKeyword || undefined,
      experience_min: activeLevel?.min !== undefined && activeLevel.min > 0 ? activeLevel.min : undefined,
      max_experience: activeLevel?.max,
      work_model: workModel || undefined,
      job_type: jobType || undefined,
      roles: roles.length ? roles : undefined,
      posted_within_days: datePosted ? Number(datePosted) : undefined,
      match_mode: matchMode,
      sources: sourcesSubset,
    });
  }, [location, titleKeyword, activeLevel, roles, workModel, jobType, datePosted, matchMode, sourcesSubset]);

  // Debounced facet/count preview over the public catalogue.
  useEffect(() => {
    const t = setTimeout(() => {
      searchJobs({
        q: titleKeyword || undefined,
        location: location || undefined,
        work_model: workModel || undefined,
        job_type: jobType || undefined,
        roles: roles.length ? roles : undefined,
        posted_within_days: datePosted ? Number(datePosted) : undefined,
        experience_min: activeLevel?.min,
        experience_max: activeLevel?.max,
        sources: sourcesSubset,
        limit: 1,
        include_facets: true,
      })
        .then((res) => {
          setPreviewTotal(res.total);
          if (res.facets) setFacets(res.facets);
        })
        .catch(() => setPreviewTotal(null));
    }, 400);
    return () => clearTimeout(t);
  }, [location, titleKeyword, activeLevel, roles, workModel, jobType, datePosted, sourcesSubset]);

  const toggleRole = useCallback((role: string) => {
    setRoles((prev) => (prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]));
  }, []);

  const togglePortal = useCallback((company: string) => {
    setSelectedPortals((prev) =>
      prev.includes(company) ? prev.filter((c) => c !== company) : [...prev, company]
    );
  }, []);

  const allSelected = portals.length > 0 && selectedPortals.length === portals.length;
  const toggleAll = useCallback(() => {
    setSelectedPortals(allSelected ? [] : portals.map((p) => p.company));
  }, [allSelected, portals]);

  const toggleGroup = useCallback(
    (group: Portal["group"]) => {
      const members = portals.filter((p) => p.group === group).map((p) => p.company);
      setSelectedPortals((prev) => {
        const allOn = members.every((m) => prev.includes(m));
        return allOn ? prev.filter((c) => !members.includes(c)) : [...new Set([...prev, ...members])];
      });
    },
    [portals]
  );

  const resetAll = useCallback(() => {
    setLocation(""); setTitleKeyword(""); setExpLevel(""); setRoles([]);
    setWorkModel(""); setJobType(""); setDatePosted(""); setMatchMode("semantic");
    setSelectedPortals(portals.map((p) => p.company));
  }, [portals]);

  // ── Active-filter pills (Amazon-style: state is always visible) ──
  const pills: Pill[] = [
    ...roles.map((r) => ({ key: `role:${r}`, label: r })),
    ...(location ? [{ key: "location", label: location }] : []),
    ...(titleKeyword ? [{ key: "keyword", label: `“${titleKeyword}”` }] : []),
    ...(expLevel ? [{ key: "exp", label: activeLevel?.label ?? "" }] : []),
    ...(workModel ? [{ key: "work", label: WORK_MODELS.find((w) => w.value === workModel)?.label ?? workModel }] : []),
    ...(jobType ? [{ key: "type", label: JOB_TYPES.find((j) => j.value === jobType)?.label ?? jobType }] : []),
    ...(datePosted ? [{ key: "date", label: DATE_POSTED.find((d) => d.value === datePosted)?.label ?? "" }] : []),
    ...(sourcesSubset ? [{ key: "portals", label: `${sourcesSubset.length} portals` }] : []),
  ];

  const removePill = useCallback((key: string) => {
    if (key.startsWith("role:")) toggleRole(key.slice(5));
    else if (key === "location") setLocation("");
    else if (key === "keyword") setTitleKeyword("");
    else if (key === "exp") setExpLevel("");
    else if (key === "work") setWorkModel("");
    else if (key === "type") setJobType("");
    else if (key === "date") setDatePosted("");
    else if (key === "portals") setSelectedPortals(portals.map((p) => p.company));
  }, [toggleRole, portals]);

  const jobTypeOptions = useMemo<DropdownOption[]>(
    () => JOB_TYPES.map((o) => ({
      ...o,
      hint: o.value ? facets?.job_types?.[o.value] ?? "" : "",
    })),
    [facets]
  );
  const dateOptions = useMemo<DropdownOption[]>(
    () => DATE_POSTED.map((d) => ({
      ...d,
      hint: d.value && DATE_FACET_KEY[d.value] ? facets?.posted_within?.[DATE_FACET_KEY[d.value]] ?? "" : "",
    })),
    [facets]
  );

  const roleOptions = opts?.roles ?? [];

  const labelCls = "block text-[10px] font-semibold text-fg/55 uppercase tracking-[0.18em] mb-2";

  return (
    <div className={`space-y-6 ${disabled ? "opacity-50 pointer-events-none" : ""}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">Refine results</span>
        <span className="flex items-center gap-3">
          {previewTotal !== null && (
            <span className="text-xs text-muted-foreground">
              <span className="font-bold text-foreground tabular-nums">{previewTotal}</span> jobs match
            </span>
          )}
          <button type="button" onClick={resetAll} className="text-[10px] text-primary hover:underline">
            Reset filters
          </button>
        </span>
      </div>

      {/* Active filters — always visible, individually removable */}
      <FilterPills pills={pills} onRemove={removePill} onClear={resetAll} />

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
                  ? "bg-primary text-primary-foreground border-transparent"
                  : "bg-muted/50 text-foreground border-border hover:border-primary/50 hover:bg-muted"
              }`}
            >
              <span className="text-xs font-bold">{m.label}</span>
              <span className={`text-[10px] ${matchMode === m.v ? "text-primary-foreground/80" : "text-muted-foreground"}`}>{m.hint}</span>
            </motion.button>
          ))}
        </div>
        <p className="text-[10px] text-fg/40 mt-2 leading-relaxed">
          {matchMode === "direct"
            ? "Direct Filter ranks by how many of a job's listed skills you have — best when you've set location/experience and want clean, predictable results."
            : "Smart Match blends semantic relevance with skill overlap for a holistic score."}
        </p>
      </div>

      {/* Role category — software-engineering taxonomy, multi-select w/ counts */}
      {roleOptions.length > 0 && (
        <div>
          <label className={labelCls}>
            Role <span className="text-fg/30 normal-case tracking-normal">· pick any that fit</span>
          </label>
          <div className="flex flex-wrap gap-2">
            {roleOptions.map((role) => {
              const on = roles.includes(role);
              const count = facets?.roles?.[role];
              return (
                <motion.button
                  key={role} type="button" disabled={disabled}
                  whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
                  onClick={() => toggleRole(role)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
                    on
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted/60 text-muted-foreground hover:text-foreground border border-border"
                  }`}
                >
                  {role}
                  {count !== undefined && (
                    <span className={`tabular-nums text-[10px] ${on ? "text-primary-foreground/75" : "text-muted-foreground/70"}`}>
                      {count}
                    </span>
                  )}
                </motion.button>
              );
            })}
          </div>
        </div>
      )}

      {/* Experience level — single choice, Amazon industry_experience style */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">Experience Required</label>
          {facets?.experience_ranges && expLevel === "" && (
            <span className="text-[10px] text-muted-foreground tabular-nums">
              {Object.entries(facets.experience_ranges).map(([k, v]) => `${k}: ${v}`).join(" · ")}
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {EXPERIENCE_LEVELS.map((l) => {
            const on = expLevel === l.id;
            return (
              <motion.button
                key={l.id || "any"} type="button" disabled={disabled}
                whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                onClick={() => setExpLevel(l.id)}
                className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all ${
                  on
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted/60 text-muted-foreground hover:text-foreground border border-border"
                }`}
              >
                {l.label}
              </motion.button>
            );
          })}
        </div>
      </div>

      {/* Location */}
      <div>
        <label className={labelCls}>Location</label>
        <Dropdown value={location} onChange={setLocation} options={locationOptions} searchable
          disabled={disabled} placeholder="Type or pick a location…" ariaLabel="Location" />
      </div>

      {/* Work Model — with live counts */}
      <div>
        <label className={labelCls}>Work Model</label>
        <div className="grid grid-cols-4 gap-2">
          {WORK_MODELS.map((m) => {
            const count = m.value ? facets?.work_model?.[m.value] : undefined;
            return (
              <motion.button
                whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                key={m.label} type="button" onClick={() => setWorkModel(m.value)}
                className={`px-2 py-1.5 rounded-md text-xs font-semibold transition-all ${
                  workModel === m.value
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                {m.label}
                {count !== undefined && (
                  <span className={`ml-1 tabular-nums text-[10px] ${workModel === m.value ? "text-primary-foreground/75" : "text-muted-foreground/70"}`}>
                    {count}
                  </span>
                )}
              </motion.button>
            );
          })}
        </div>
      </div>

      {/* Job Type + Date Posted (animated dropdowns, count-annotated) */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Job Type</label>
          <Dropdown value={jobType} onChange={setJobType} options={jobTypeOptions} disabled={disabled} ariaLabel="Job type" />
        </div>
        <div>
          <label className={labelCls}>Date Posted</label>
          <Dropdown value={datePosted} onChange={setDatePosted} options={dateOptions} disabled={disabled} ariaLabel="Date posted" />
        </div>
      </div>

      {/* Free-text title keyword (raw titles remain searchable) */}
      <div>
        <label className={labelCls}>
          Title Keyword <span className="text-fg/30 normal-case tracking-normal">· optional</span>
        </label>
        <Dropdown value={titleKeyword} onChange={setTitleKeyword} options={titleOptions} searchable
          disabled={disabled} placeholder="Type or pick a title…" ariaLabel="Title keyword" />
      </div>

      {/* Career Portals — grouped: Indian / Global / Aggregators */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">Career Portals</label>
          {portals.length > 0 && (
            <button type="button" onClick={toggleAll}
              className="text-[10px] text-primary hover:underline">
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
          <div className="space-y-4">
            {PORTAL_GROUPS.map((g) => {
              const members = portals.filter((p) => p.group === g.id);
              if (members.length === 0) return null;
              const groupAllOn = members.every((p) => selectedPortals.includes(p.company));
              return (
                <div key={g.id}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-semibold text-fg/45 uppercase tracking-wider">
                      {g.label} <span className="normal-case tracking-normal">· {members.length}</span>
                    </span>
                    <button type="button" onClick={() => toggleGroup(g.id)}
                      className="text-[10px] text-muted-foreground hover:text-foreground transition-colors">
                      {groupAllOn ? "None" : "All"}
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {members.map((portal) => {
                      const on = selectedPortals.includes(portal.company);
                      return (
                        <motion.button
                          whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}
                          key={portal.company} type="button" onClick={() => togglePortal(portal.company)}
                          className={`flex items-center gap-2.5 px-3 py-2 rounded-lg border transition-all ${
                            on ? "bg-muted/50 border-primary"
                               : "bg-card border-border hover:bg-muted/30"
                          }`}
                        >
                          <div className={`w-3.5 h-3.5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-all ${on ? "border-primary bg-primary" : "border-border"}`}>
                            {on && (
                              <svg className="w-2.5 h-2.5 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                              </svg>
                            )}
                          </div>
                          <p className="flex-1 text-left text-xs font-medium text-foreground truncate">{portal.company}</p>
                          <span className={`flex-shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${
                            portal.live
                              ? "bg-secondary text-secondary-foreground"
                              : "bg-muted text-muted-foreground"
                          }`}>
                            {portal.live ? "Live" : "Curated"}
                          </span>
                        </motion.button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
