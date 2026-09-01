"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import { useClickOutside, useEscapeKey } from "@/hooks/use-dismiss";

export interface ComboboxOption {
  value: string;
  label: string;
  sublabel?: string;
}

/** Searchable single-select, styled like Select/Input. Unlike a free-text
 * input, committing a value requires picking one of `options` - Enter only
 * confirms the highlighted option, so a typo can never reach `onChange`.
 * Follows the same hand-rolled overlay pattern as DropdownMenu/CommandMenu
 * (see hooks/use-dismiss.ts) rather than adding a combobox dependency. */
export function Combobox({
  id,
  value,
  options,
  onChange,
  placeholder = "Search...",
  ariaLabel,
  emptyText = "No matches found.",
  disabled,
  describedBy,
  invalid,
}: {
  id: string;
  value: string;
  options: ComboboxOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  ariaLabel?: string;
  emptyText?: string;
  disabled?: boolean;
  describedBy?: string;
  invalid?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const selected = useMemo(() => options.find((o) => o.value === value) ?? null, [options, value]);

  useClickOutside([rootRef], open, () => setOpen(false));
  useEscapeKey(open, () => setOpen(false));

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q));
  }, [options, query]);

  useEffect(() => {
    if (open) listRef.current?.children[activeIndex]?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open]);

  function openList() {
    if (disabled || open) return;
    setQuery("");
    setActiveIndex(0);
    setOpen(true);
  }

  function commit(option: ComboboxOption) {
    onChange(option.value);
    setOpen(false);
    setQuery("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter") {
        e.preventDefault();
        openList();
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtered[activeIndex]) commit(filtered[activeIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const displayValue = open ? query : (selected?.label ?? value);
  const activeId = open && filtered[activeIndex] ? `${id}-option-${activeIndex}` : undefined;

  return (
    <div ref={rootRef} className="relative">
      <div className="relative">
        <input
          id={id}
          role="combobox"
          aria-expanded={open}
          aria-controls={`${id}-listbox`}
          aria-autocomplete="list"
          aria-activedescendant={activeId}
          aria-label={ariaLabel}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          autoComplete="off"
          disabled={disabled}
          placeholder={placeholder}
          value={displayValue}
          onFocus={openList}
          onClick={openList}
          onChange={(e) => {
            setQuery(e.target.value);
            setActiveIndex(0);
            if (!open) setOpen(true);
          }}
          onKeyDown={handleKeyDown}
          className={cn(
            "flex h-9 w-full rounded-md border bg-input px-3 py-1 pr-8 text-sm text-foreground shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50",
            invalid ? "border-error-400 focus-visible:ring-error-400" : "border-border-strong",
          )}
        />
        <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
      </div>
      {open && (
        <div
          ref={listRef}
          id={`${id}-listbox`}
          role="listbox"
          aria-label={ariaLabel}
          className="absolute z-40 mt-1.5 max-h-64 w-full overflow-y-auto rounded-lg border border-border bg-surface-raised p-1 shadow-popover animate-slide-up motion-reduce:animate-none"
        >
          {filtered.length === 0 && <p className="px-3 py-4 text-center text-sm text-muted-foreground">{emptyText}</p>}
          {filtered.map((option, i) => (
            <button
              key={option.value}
              id={`${id}-option-${i}`}
              type="button"
              role="option"
              aria-selected={option.value === value}
              onMouseEnter={() => setActiveIndex(i)}
              onClick={() => commit(option)}
              className={cn(
                "flex w-full flex-col items-start rounded-md px-3 py-2 text-left text-sm transition-colors",
                i === activeIndex ? "bg-accent text-accent-foreground" : "text-foreground hover:bg-muted",
              )}
            >
              <span className="font-medium">{option.label}</span>
              {option.sublabel && <span className="text-xs text-muted-foreground">{option.sublabel}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
