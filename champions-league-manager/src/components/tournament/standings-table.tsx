"use client";

import { motion } from "framer-motion";

import { TeamCrest } from "@/components/tournament/team-crest";
import { useStandings, useTeamMap, useTournament } from "@/hooks/use-tournament";
import { BAND_LABEL, qualificationBand } from "@/lib/standings";
import type { QualificationBand } from "@/lib/types";
import { cn, formatSigned } from "@/lib/utils";

const BAND_ACCENT: Record<QualificationBand, string> = {
  direct: "bg-mint",
  playoff: "bg-primary",
  out: "bg-rose/60",
};

const FORM_STYLE = {
  W: "bg-mint/20 text-mint",
  D: "bg-white/10 text-muted-foreground",
  L: "bg-rose/20 text-rose",
} as const;

const FORM_LABEL = { W: "Victoire", D: "Nul", L: "Défaite" } as const;

export function StandingsTable({ showBands = true }: { showBands?: boolean }) {
  const tournament = useTournament();
  const standings = useStandings();
  const teams = useTeamMap();

  if (!tournament) return null;

  return (
    <div className="glass overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-sm">
          <caption className="sr-only">
            Classement de la phase de ligue, trié par points puis différence de buts puis buts
            marqués
          </caption>
          <thead>
            <tr className="border-b border-white/10 text-left">
              {[
                { key: "pos", label: "#", className: "w-10 text-center" },
                { key: "club", label: "Club", className: "min-w-[150px]" },
                { key: "j", label: "J", className: "w-9 text-center" },
                { key: "g", label: "G", className: "w-9 text-center" },
                { key: "n", label: "N", className: "w-9 text-center" },
                { key: "p", label: "P", className: "w-9 text-center" },
                { key: "bm", label: "BM", className: "hidden w-10 text-center sm:table-cell" },
                { key: "be", label: "BE", className: "hidden w-10 text-center sm:table-cell" },
                { key: "diff", label: "Diff", className: "w-12 text-center" },
                { key: "pts", label: "Pts", className: "w-12 text-center" },
                { key: "form", label: "Forme", className: "hidden w-28 lg:table-cell" },
              ].map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className={cn(
                    "px-2 py-2.5 font-display text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground",
                    column.className,
                  )}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {standings.map((row, index) => {
              const team = teams.get(row.teamId);
              const band = qualificationBand(row.rank, tournament.bracketSize);

              return (
                <motion.tr
                  key={row.teamId}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: Math.min(index * 0.012, 0.25) }}
                  className="border-b border-white/[0.06] transition-colors last:border-0 hover:bg-white/[0.035]"
                >
                  <td className="relative px-2 py-2 text-center">
                    {showBands ? (
                      <span
                        aria-hidden
                        className={cn(
                          "absolute inset-y-1 left-0 w-0.5 rounded-full",
                          BAND_ACCENT[band],
                        )}
                      />
                    ) : null}
                    <span className="tabular font-display text-sm font-bold">{row.rank}</span>
                  </td>

                  <td className="px-2 py-2">
                    <span className="flex items-center gap-2">
                      <TeamCrest team={team} size="xs" />
                      <span className="min-w-0 truncate font-medium">{team?.name}</span>
                      {showBands ? (
                        <span className="sr-only">{BAND_LABEL[band]}</span>
                      ) : null}
                    </span>
                  </td>

                  <td className="tabular px-2 py-2 text-center text-muted-foreground">{row.played}</td>
                  <td className="tabular px-2 py-2 text-center">{row.wins}</td>
                  <td className="tabular px-2 py-2 text-center">{row.draws}</td>
                  <td className="tabular px-2 py-2 text-center">{row.losses}</td>
                  <td className="tabular hidden px-2 py-2 text-center sm:table-cell">{row.goalsFor}</td>
                  <td className="tabular hidden px-2 py-2 text-center sm:table-cell">
                    {row.goalsAgainst}
                  </td>
                  <td
                    className={cn(
                      "tabular px-2 py-2 text-center",
                      row.goalDiff > 0 && "text-mint",
                      row.goalDiff < 0 && "text-rose",
                    )}
                  >
                    {formatSigned(row.goalDiff)}
                  </td>
                  <td className="tabular px-2 py-2 text-center font-display font-bold">
                    {row.points}
                  </td>
                  <td className="hidden px-2 py-2 lg:table-cell">
                    <span className="flex gap-1">
                      {row.form.length === 0 ? (
                        <span className="text-xs text-muted-foreground">—</span>
                      ) : (
                        row.form.map((result, position) => (
                          <span
                            key={`${row.teamId}-${position}`}
                            title={FORM_LABEL[result]}
                            className={cn(
                              "grid size-4 place-items-center rounded-sm text-[9px] font-bold",
                              FORM_STYLE[result],
                            )}
                          >
                            {result}
                            <span className="sr-only">{FORM_LABEL[result]}</span>
                          </span>
                        ))
                      )}
                    </span>
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {showBands ? (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/10 px-3 py-2.5">
          {(["direct", "playoff", "out"] as const).map((band) => (
            <span key={band} className="flex items-center gap-2 text-xs text-muted-foreground">
              <span aria-hidden className={cn("h-2.5 w-0.5 rounded-full", BAND_ACCENT[band])} />
              {BAND_LABEL[band]}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
