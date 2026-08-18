"use client";

import { cn } from "@/lib/utils";

type ScoreInputProps = {
  value: number | null;
  onChange: (value: number | null) => void;
  label: string;
  tone?: "default" | "pens";
  className?: string;
};

/** Compact goal field: empty means "not played yet", never zero by default. */
export function ScoreInput({ value, onChange, label, tone = "default", className }: ScoreInputProps) {
  return (
    <input
      type="number"
      inputMode="numeric"
      min={0}
      max={99}
      aria-label={label}
      value={value === null ? "" : value}
      placeholder="–"
      onChange={(event) => {
        const raw = event.target.value;
        if (raw === "") {
          onChange(null);
          return;
        }
        const parsed = Number.parseInt(raw, 10);
        if (Number.isNaN(parsed)) return;
        onChange(Math.min(99, Math.max(0, parsed)));
      }}
      className={cn(
        "rounded-md border text-center font-display font-bold tabular-nums transition-colors",
        "placeholder:font-normal placeholder:text-muted-foreground/60",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
        tone === "pens"
          ? "size-8 border-white/12 bg-white/[0.03] text-xs hover:border-white/20 focus-visible:border-primary/60"
          : "h-10 w-11 border-white/12 bg-white/[0.05] text-base hover:border-white/25 focus-visible:border-primary/60 focus-visible:bg-white/[0.09]",
        className,
      )}
    />
  );
}
