"use client";

import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

export interface DropdownOption {
  value: string;
  label: string;
  hint?: string | number; // e.g. facet count
}

interface DropdownProps {
  value: string;
  onChange: (value: string) => void;
  options: DropdownOption[];
  placeholder?: string;
  /** Allow typing to filter + free-text entry (combobox mode). */
  searchable?: boolean;
  disabled?: boolean;
  ariaLabel?: string;
}

/**
 * Animated, theme-aware dropdown / combobox. Replaces native <select> so it can
 * animate and (in searchable mode) filter a long list while still allowing a
 * free-text value the user types. Keyboard: ↑/↓ move, Enter selects, Esc closes.
 */
export default function Dropdown({
  value,
  onChange,
  options,
  placeholder = "Select…",
  searchable = false,
  disabled = false,
  ariaLabel,
}: DropdownProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const selectedLabel = options.find((o) => o.value === value)?.label ?? value;

  const filtered =
    searchable && query
      ? options.filter((o) => o.label.toLowerCase().includes(query.toLowerCase()))
      : options;

  // Close on outside click.
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

  const commit = (val: string) => {
    onChange(val);
    setOpen(false);
    setQuery("");
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!open && (e.key === "ArrowDown" || e.key === "Enter")) {
      setOpen(true);
      return;
    }
    if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (searchable && query && !filtered[active]) commit(query);
      else if (filtered[active]) commit(filtered[active].value);
    }
  };

  const buttonText = value ? selectedLabel : placeholder;

  return (
    <div ref={rootRef} className="relative" onKeyDown={onKeyDown}>
      {searchable && open ? (
        <input
          autoFocus
          type="text"
          value={query}
          disabled={disabled}
          placeholder={selectedLabel || placeholder}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
        />
      ) : (
        <button
          type="button"
          disabled={disabled}
          aria-label={ariaLabel}
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
          className="w-full px-4 py-2.5 bg-card border border-border rounded-md text-sm text-left flex items-center justify-between gap-2 hover:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-ring transition-all"
        >
          <span className={value ? "text-foreground truncate" : "text-muted-foreground truncate"}>{buttonText}</span>
          <motion.svg
            animate={{ rotate: open ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            className="w-4 h-4 text-muted-foreground shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </motion.svg>
        </button>
      )}

      <AnimatePresence>
        {open && (
          <motion.ul
            id={listId}
            role="listbox"
            initial={{ opacity: 0, y: -10, scaleY: 0.85 }}
            animate={{ opacity: 1, y: 0, scaleY: 1 }}
            exit={{ opacity: 0, y: -10, scaleY: 0.9 }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
            className="absolute z-40 mt-2 w-full max-h-60 overflow-y-auto bg-popover text-popover-foreground border border-border shadow-md rounded-md p-1.5 origin-top"
          >
            {filtered.length === 0 && (
              <li className="px-3 py-2 text-xs text-muted-foreground">
                {searchable && query ? `Press Enter to use “${query}”` : "No options"}
              </li>
            )}
            {filtered.map((opt, i) => {
              const isSel = opt.value === value;
              const isActive = i === active;
              return (
                <motion.li
                  key={`${opt.value}-${i}`}
                  role="option"
                  aria-selected={isSel}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => commit(opt.value)}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.15, delay: Math.min(i * 0.015, 0.2) }}
                  className={`flex items-center justify-between gap-2 px-3 py-2 rounded-sm text-sm cursor-pointer transition-colors ${
                    isActive ? "bg-accent text-accent-foreground" : "text-foreground"
                  }`}
                >
                  <span className="truncate flex items-center gap-2">
                    {isSel && (
                      <svg className="w-3.5 h-3.5 text-primary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                    {opt.label}
                  </span>
                  {opt.hint !== undefined && opt.hint !== "" && (
                    <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">{opt.hint}</span>
                  )}
                </motion.li>
              );
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
