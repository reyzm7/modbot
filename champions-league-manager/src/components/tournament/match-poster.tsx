"use client";

import { AnimatePresence, motion } from "framer-motion";

import { TeamCrest } from "@/components/tournament/team-crest";
import type { Team } from "@/lib/types";
import { cn, colorFromName } from "@/lib/utils";

type MatchPosterProps = {
  home?: Team | null;
  away?: Team | null;
  label?: string;
  footnote?: string;
  animate?: boolean;
  className?: string;
  /** Permet de dévoiler l'adversaire après coup, pour le suspense du tirage. */
  showAway?: boolean;
};

/**
 * Marquage réglementaire. `slice` préserve les proportions et rogne le
 * débordement : c'est indispensable, sinon le rond central s'aplatit en ellipse
 * dès que la carte n'a pas exactement le rapport du viewBox.
 */
function PitchLines() {
  return (
    <svg
      viewBox="0 0 460 180"
      preserveAspectRatio="xMidYMid slice"
      className="pointer-events-none absolute inset-0 size-full"
      aria-hidden
    >
      <g fill="none" stroke="white" strokeOpacity="0.3" strokeWidth="1.6">
        <rect x="8" y="8" width="444" height="164" rx="1" />
        <line x1="230" y1="8" x2="230" y2="172" />
        <circle cx="230" cy="90" r="40" />
        <rect x="8" y="40" width="60" height="100" />
        <rect x="8" y="63" width="24" height="54" />
        <rect x="392" y="40" width="60" height="100" />
        <rect x="428" y="63" width="24" height="54" />
        <path d="M8 22 A14 14 0 0 0 22 8" />
        <path d="M438 8 A14 14 0 0 0 452 22" />
        <path d="M8 158 A14 14 0 0 1 22 172" />
        <path d="M452 158 A14 14 0 0 0 438 172" />
      </g>
      <circle cx="230" cy="90" r="2.6" fill="white" fillOpacity="0.4" />
    </svg>
  );
}

export function MatchPoster({
  home,
  away,
  label,
  footnote,
  animate = true,
  className,
  showAway = true,
}: MatchPosterProps) {
  const homeColor = home?.name ? colorFromName(home.name) : "hsl(223 100% 59%)";
  const awayColor = away?.name ? colorFromName(away.name) : "hsl(258 90% 66%)";

  const enter = animate
    ? { initial: { opacity: 0, scale: 0.94, y: 18 }, animate: { opacity: 1, scale: 1, y: 0 } }
    : {};

  return (
    <motion.div
      {...enter}
      transition={{ type: "spring", stiffness: 220, damping: 26 }}
      className={cn(
        "relative flex min-h-[300px] flex-col justify-center overflow-hidden rounded-xl border border-white/12 shadow-glass sm:min-h-[340px]",
        className,
      )}
    >
      {/* Pelouse : bandes de tonte alternées, comme un terrain fraîchement passé. */}
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            "repeating-linear-gradient(90deg, hsl(152 46% 9%) 0 6.25%, hsl(150 40% 13%) 6.25% 12.5%)",
        }}
      />
      {/* Projecteurs : la lumière tombe des deux côtés, comme en nocturne. */}
      <div
        aria-hidden
        className="absolute inset-0 bg-[radial-gradient(80%_120%_at_20%_-20%,hsl(152_60%_42%/0.42),transparent_58%),radial-gradient(80%_120%_at_80%_-20%,hsl(152_60%_42%/0.34),transparent_58%)]"
      />
      <PitchLines />
      {/* Vignette : sans elle, la pelouse paraît plate et délavée sur les bords. */}
      <div
        aria-hidden
        className="absolute inset-0 bg-[radial-gradient(115%_95%_at_50%_45%,transparent_38%,hsl(155_60%_4%/0.72)_100%)]"
      />

      {/* Halos aux couleurs des clubs, discrets : ils colorent sans dominer. */}
      <div
        aria-hidden
        className="absolute inset-y-0 left-0 w-2/5 opacity-30 mix-blend-screen"
        style={{ background: `radial-gradient(60% 70% at 22% 50%, ${homeColor}, transparent 72%)` }}
      />
      {showAway ? (
        <motion.div
          aria-hidden
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.3 }}
          transition={{ duration: 0.6 }}
          className="absolute inset-y-0 right-0 w-2/5 mix-blend-screen"
          style={{
            background: `radial-gradient(60% 70% at 78% 50%, ${awayColor}, transparent 72%)`,
          }}
        />
      ) : null}

      <div className="relative px-4 py-6 sm:px-8 sm:py-8">
        {label ? (
          <p className="mb-5 text-center text-[10px] font-semibold uppercase tracking-[0.24em] text-white/70">
            {label}
          </p>
        ) : null}

        <div className="flex items-center gap-2 sm:gap-4">
          <motion.div
            initial={{ opacity: 0, x: -24 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1, type: "spring", stiffness: 260, damping: 24 }}
            className="flex min-w-0 flex-1 flex-col items-center gap-2.5"
          >
            <span
              className="rounded-full p-1 ring-2 ring-offset-2 ring-offset-transparent"
              style={{ boxShadow: `0 0 26px -4px ${homeColor}` }}
            >
              <TeamCrest team={home} size="xl" />
            </span>
            <span className="w-full truncate text-center font-display text-sm font-bold tracking-tight text-white sm:text-lg">
              {home?.name}
            </span>
            <span className="h-0.5 w-10 rounded-full" style={{ background: homeColor }} />
          </motion.div>

          <div className="relative grid size-16 shrink-0 place-items-center rounded-full border border-white/30 bg-[hsl(152_50%_8%/0.75)] backdrop-blur-sm sm:size-20">
            <span className="font-display text-sm font-black tracking-widest text-white/90 sm:text-base">
              VS
            </span>
          </div>

          <div className="flex min-w-0 flex-1 flex-col items-center gap-2.5">
            <AnimatePresence mode="wait">
              {showAway ? (
                <motion.div
                  key="away"
                  initial={{ opacity: 0, x: 24, scale: 0.9 }}
                  animate={{ opacity: 1, x: 0, scale: 1 }}
                  transition={{ type: "spring", stiffness: 260, damping: 22 }}
                  className="flex w-full flex-col items-center gap-2.5"
                >
                  <span
                    className="rounded-full p-1"
                    style={{ boxShadow: `0 0 26px -4px ${awayColor}` }}
                  >
                    <TeamCrest team={away} size="xl" />
                  </span>
                  <span className="w-full truncate text-center font-display text-sm font-bold tracking-tight text-white sm:text-lg">
                    {away?.name}
                  </span>
                  <span className="h-0.5 w-10 rounded-full" style={{ background: awayColor }} />
                </motion.div>
              ) : (
                <motion.div
                  key="pending"
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="flex w-full flex-col items-center gap-2.5"
                >
                  <motion.span
                    animate={{ opacity: [0.35, 0.85, 0.35] }}
                    transition={{ duration: 0.85, repeat: Infinity, ease: "easeInOut" }}
                    className="grid size-16 place-items-center rounded-full border-2 border-dashed border-white/45 font-display text-2xl font-black text-white/75 sm:size-20"
                  >
                    ?
                  </motion.span>
                  <span className="text-center text-xs uppercase tracking-[0.2em] text-white/65">Adversaire…</span>
                  <span className="h-0.5 w-10 rounded-full bg-white/20" />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {footnote ? (
          <p className="mt-6 text-center text-xs text-white/60">{footnote}</p>
        ) : null}
      </div>
    </motion.div>
  );
}
