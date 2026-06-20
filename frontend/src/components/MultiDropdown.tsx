"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { DropdownOption } from "./Dropdown";

interface MultiDropdownProps {
  values: string[];
  onChange: (values: string[]) => void;
  options: DropdownOption[];
  placeholder?: string;
  /** Allow typing to filter and add free-text values not in the list. */
  searchable?: boolean;
  disabled?: boolean;
  ariaLabel?: string;
}

/**
 * Animated multi-select combobox. Selected values render as removable chips;
 * typing filters the list and (searchable) lets you add a free-text value with
 * Enter. Used for Location so the user can pick several places at once.
 */
export default function MultiDropdown({
  values,
  onChange,
  options,
  placeholder = "Add…",
  searchable = true,
  disabled = false,
  ariaLabel,
}: MultiDropdownProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();

  const filtered = useMemo(() => {
    const sel = new Set(values.map((v) => v.toLowerCase()));
    return options.filter(
      (o) =>
        !sel.has(o.value.toLowerCase()) &&
        (!query || o.label.toLowerCase().includes(query.toLowerCase()))
    );
  }, [options, values, query]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const add = (val: string) => {
    const v = val.trim();
    if (v && !values.some((x) => x.toLowerCase() === v.toLowerCase())) {
      onChange([...values, v]);
    }
    setQuery("");
    setActive(0);
    inputRef.current?.focus();
  };

  const remove = (val: string) => onChange(values.filter((v) => v !== val));

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtered[active]) add(filtered[active].value);
      else if (searchable && query) add(query);
    } else if (e.key === "Backspace" && !query && values.length) {
      remove(values[values.length - 1]);
    }
  };

  return (
    <div ref={rootRef} className="relative" onKeyDown={onKeyDown}>
      <div
        onClick={() => { if (!disabled) { setOpen(true); inputRef.current?.focus(); } }}
        className={`min-h-[42px] w-full px-2.5 py-1.5 bg-fg/[0.04] border rounded-xl flex flex-wrap items-center gap-1.5 cursor-text transition-all ${
          open ? "border-ring ring-2 ring-ring/20" : "border-fg/10 hover:bg-fg/[0.06]"
        } ${disabled ? "opacity-50 pointer-events-none" : ""}`}
      >
        <AnimatePresence initial={false}>
          {values.map((v) => (
            <motion.span
              key={v}
              layout
              initial={{ opacity: 0, scale: 0.7 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.7 }}
              transition={{ type: "spring", stiffness: 500, damping: 30 }}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-xs font-medium bg-secondary text-secondary-foreground border border-border"
            >
              {v}
              <button type="button" onClick={(e) => { e.stopPropagation(); remove(v); }}
                className="hover:text-destructive transition-colors" aria-label={`Remove ${v}`}>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </motion.span>
          ))}
        </AnimatePresence>
        <input
          ref={inputRef}
          type="text"
          value={query}
          disabled={disabled}
          placeholder={values.length === 0 ? placeholder : ""}
          onFocus={() => setOpen(true)}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(0); }}
          className="flex-1 min-w-[80px] bg-transparent text-sm text-fg/90 placeholder:text-fg/40 focus:outline-none py-1"
          role="combobox" aria-expanded={open} aria-controls={listId} aria-label={ariaLabel}
        />
      </div>

      <AnimatePresence>
        {open && (
          <motion.ul
            id={listId}
            role="listbox"
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className="absolute z-40 mt-2 w-full max-h-60 overflow-y-auto glass-popover rounded-xl p-1.5 origin-top"
          >
            {filtered.length === 0 && (
              <li className="px-3 py-2 text-xs text-fg/40">
                {searchable && query ? `Press Enter to add “${query}”` : "No more options"}
              </li>
            )}
            {filtered.slice(0, 50).map((opt, i) => (
              <motion.li
                key={`${opt.value}-${i}`}
                role="option"
                aria-selected={false}
                onMouseEnter={() => setActive(i)}
                onClick={() => add(opt.value)}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.15, delay: Math.min(i * 0.012, 0.18) }}
                className={`flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors ${
                  i === active ? "bg-secondary text-fg" : "text-fg/70"
                }`}
              >
                <span className="truncate">{opt.label}</span>
                {opt.hint !== undefined && opt.hint !== "" && (
                  <span className="text-[10px] text-fg/35 tabular-nums shrink-0">{opt.hint}</span>
                )}
              </motion.li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
