"use client";

import { useEffect, useMemo, useState } from "react";
import { getFilterOptions, type FilterOptions } from "@/lib/api";
import type { DropdownOption } from "@/components/Dropdown";

/**
 * Fetches the live filter-option catalogue once and derives the dropdown option
 * lists shared by the match (FilterPanel) and browse (AdvancedSearchPanel)
 * filter UIs — the countries-first location dedupe in particular was duplicated
 * verbatim in both.
 */
export function useFilterOptions() {
  const [opts, setOpts] = useState<FilterOptions | null>(null);

  useEffect(() => {
    getFilterOptions().then(setOpts).catch(console.error);
  }, []);

  // Countries first (pick a whole country), then specific cities. Dedupe by
  // lowercased value so a country and an identically named data location don't
  // produce duplicate options / colliding React keys.
  const locationOptions = useMemo<DropdownOption[]>(() => {
    const seen = new Set<string>();
    const out: DropdownOption[] = [];
    for (const c of opts?.countries || []) {
      const k = c.toLowerCase();
      if (seen.has(k)) continue;
      seen.add(k);
      out.push({ value: c, label: `${c} — all`, hint: "country" });
    }
    for (const l of opts?.locations || []) {
      const k = l.toLowerCase();
      if (seen.has(k)) continue;
      seen.add(k);
      out.push({ value: l, label: l });
    }
    return out;
  }, [opts]);

  const titleOptions = useMemo<DropdownOption[]>(
    () => (opts?.titles || []).map((t) => ({ value: t, label: t })),
    [opts]
  );
  const companyOptions = useMemo<DropdownOption[]>(
    () => (opts?.companies || []).map((c) => ({ value: c, label: c })),
    [opts]
  );

  return { opts, locationOptions, titleOptions, companyOptions };
}
