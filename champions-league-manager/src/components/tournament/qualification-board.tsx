"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck, Swords, XCircle } from "lucide-react";

import { TeamCrest } from "@/components/tournament/team-crest";
import { Badge } from "@/components/ui/badge";
import { useStandings, useTeamMap, useTournament } from "@/hooks/use-tournament";
import { qualificationBand } from "@/lib/standings";
import type { QualificationBand } from "@/lib/types";
import { cn, formatSigned } from "@/lib/utils";

const GROUPS: Array<{
  band: QualificationBand;
  title: string;
  caption: string;
  icon: typeof ShieldCheck;
  accent: string;
  border: string;
}> = [
  {
    band: "direct",
    title: "Qualifiés",
    caption: "Directement au tableau final",
    icon: ShieldCheck,
    accent: "text-mint",
    border: "border-mint/30 bg-mint/[0.05]",
  },
  {
    band: "playoff",
    title: "Barrages",
    caption: "Un tour de plus à franchir",
    icon: Swords,
    accent: "text-primary",
    border: "border-primary/30 bg-primary/[0.05]",
  },
  {
    band: "out",
    title: "Éliminés",
    caption: "L'aventure s'arrête ici",
    icon: XCircle,
    accent: "text-rose",
    border: "border-rose/25 bg-rose/[0.04]",
  },
];

export function QualificationBoard() {
  const tournament = useTournament();
  const standings = useStandings();
  const teams = useTeamMap();

  const grouped = useMemo(() => {
    if (!tournament) return new Map<QualificationBand, typeof standings>();
    const map = new Map<QualificationBand, typeof standings>();
    for (const row of standings) {
      const band = qualificationBand(row.rank, tournament.bracketSize);
      map.set(band, [...(map.get(band) ?? []), row]);
    }
    return map;
  }, [standings, tournament]);

  if (!tournament) return null;

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {GROUPS.map((group, groupIndex) => {
        const rows = grouped.get(group.band) ?? [];
        if (rows.length === 0) return null;

        return (
          <motion.section
            key={group.band}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: groupIndex * 0.14, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className={cn("glass surface-sheen p-4", group.border)}
            aria-labelledby={`band-${group.band}`}
          >
            <header className="mb-3 flex items-center gap-2.5">
              <group.icon className={cn("size-4 shrink-0", group.accent)} />
              <div className="min-w-0 flex-1">
                <h2
                  id={`band-${group.band}`}
                  className="font-display text-sm font-bold tracking-tight"
                >
                  {group.title}
                </h2>
                <p className="truncate text-xs text-muted-foreground">{group.caption}</p>
              </div>
              <Badge variant="neutral">{rows.length}</Badge>
            </header>

            <ol className="space-y-1">
              {rows.map((row, index) => (
                <motion.li
                  key={row.teamId}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{
                    delay: groupIndex * 0.14 + 0.18 + Math.min(index * 0.035, 0.6),
                    duration: 0.32,
                  }}
                  className="flex items-center gap-2.5 rounded-md px-2 py-1.5 transition-colors hover:bg-white/[0.04]"
                >
                  <span className="tabular w-5 shrink-0 text-right font-display text-xs font-bold text-muted-foreground">
                    {row.rank}
                  </span>
                  <TeamCrest team={teams.get(row.teamId)} size="xs" />
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">
                    {teams.get(row.teamId)?.name}
                  </span>
                  <span className="tabular shrink-0 text-xs text-muted-foreground">
                    {formatSigned(row.goalDiff)}
                  </span>
                  <span className="tabular w-6 shrink-0 text-right font-display text-sm font-bold">
                    {row.points}
                  </span>
                </motion.li>
              ))}
            </ol>

            {group.band !== "out" ? (
              <p className={cn("mt-3 flex items-center gap-1.5 text-xs", group.accent)}>
                <ArrowRight className="size-3" />
                {group.band === "direct"
                  ? tournament.knockout[1]?.name ?? "Tableau final"
                  : "Tour de barrage"}
              </p>
            ) : null}
          </motion.section>
        );
      })}
    </div>
  );
}
