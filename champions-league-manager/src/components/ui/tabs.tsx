"use client";

import * as React from "react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";

type TabItem = { value: string; label: string; icon?: React.ReactNode };

type TabsProps = {
  items: TabItem[];
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
  /** Distinguishes the sliding indicator when several tab sets share a page. */
  layoutId?: string;
};

export function Tabs({ items, value, onValueChange, className, layoutId = "tab" }: TabsProps) {
  const refs = React.useRef<Array<HTMLButtonElement | null>>([]);

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const index = items.findIndex((item) => item.value === value);
    if (index === -1) return;

    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % items.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + items.length) % items.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = items.length - 1;
    else return;

    event.preventDefault();
    onValueChange(items[next].value);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="tablist"
      onKeyDown={onKeyDown}
      className={cn(
        "inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] p-1 backdrop-blur-xl",
        className,
      )}
    >
      {items.map((item, index) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            ref={(element) => {
              refs.current[index] = element;
            }}
            role="tab"
            type="button"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onValueChange(item.value)}
            className={cn(
              "relative inline-flex items-center gap-2 rounded-md px-3.5 py-1.5 font-display text-xs font-semibold tracking-tight transition-colors sm:px-4 sm:text-sm",
              active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {active ? (
              <motion.span
                layoutId={layoutId}
                className="absolute inset-0 rounded-md border border-white/12 bg-white/[0.09]"
                transition={{ type: "spring", stiffness: 380, damping: 32 }}
              />
            ) : null}
            <span className="relative z-10 inline-flex items-center gap-2">
              {item.icon}
              {item.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
