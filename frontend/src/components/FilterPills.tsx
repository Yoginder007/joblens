"use client";

import { AnimatePresence, motion } from "framer-motion";

export interface Pill {
  key: string;
  label: string;
}

/**
 * Amazon-style active-filter pills: every applied filter is visible as a
 * removable chip, plus a "Clear all". Shared by the match wizard and the
 * browse panel so filter state always has one visual language.
 */
export default function FilterPills({
  pills,
  onRemove,
  onClear,
}: {
  pills: Pill[];
  onRemove: (key: string) => void;
  onClear: () => void;
}) {
  if (pills.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <AnimatePresence initial={false}>
        {pills.map((p) => (
          <motion.span
            key={p.key}
            layout
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }}
            transition={{ duration: 0.15 }}
            className="inline-flex items-center gap-1 pl-2.5 pr-1 py-1 rounded-full bg-secondary text-secondary-foreground text-xs font-medium max-w-full"
          >
            <span className="truncate">{p.label}</span>
            <button
              type="button"
              onClick={() => onRemove(p.key)}
              aria-label={`Remove filter: ${p.label}`}
              className="w-4 h-4 rounded-full flex items-center justify-center shrink-0 hover:bg-foreground/10 transition-colors"
            >
              <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </motion.span>
        ))}
      </AnimatePresence>
      <button
        type="button"
        onClick={onClear}
        className="text-[11px] text-muted-foreground hover:text-foreground transition-colors ml-1 underline-offset-2 hover:underline"
      >
        Clear all
      </button>
    </div>
  );
}
