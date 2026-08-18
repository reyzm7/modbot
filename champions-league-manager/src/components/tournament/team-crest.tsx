"use client";

import { cn, colorFromName, initials } from "@/lib/utils";
import type { Team } from "@/lib/types";

const SIZES = {
  xs: "size-6 text-[9px]",
  sm: "size-8 text-[10px]",
  md: "size-10 text-xs",
  lg: "size-14 text-sm",
  xl: "size-20 text-lg",
  "2xl": "size-28 text-2xl",
} as const;

type TeamCrestProps = {
  team?: Team | null;
  size?: keyof typeof SIZES;
  className?: string;
};

export function TeamCrest({ team, size = "md", className }: TeamCrestProps) {
  const name = team?.name?.trim();

  if (team?.logo) {
    return (
      <img
        src={team.logo}
        alt=""
        aria-hidden
        className={cn(
          "shrink-0 rounded-full border border-white/12 bg-white/[0.06] object-contain p-0.5",
          SIZES[size],
          className,
        )}
      />
    );
  }

  return (
    <span
      aria-hidden
      className={cn(
        "grid shrink-0 place-items-center rounded-full border border-white/12 font-display font-bold uppercase tracking-tight text-white/95",
        SIZES[size],
        className,
      )}
      style={{
        background: name
          ? `linear-gradient(160deg, ${colorFromName(name)}, rgba(6,10,26,0.85))`
          : "linear-gradient(160deg, rgba(255,255,255,0.09), rgba(6,10,26,0.7))",
      }}
    >
      {name ? initials(name) : "?"}
    </span>
  );
}
