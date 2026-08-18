"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";

import { ScoreInput } from "@/components/tournament/score-input";
import { TeamCrest } from "@/components/tournament/team-crest";
import { useTeamMap, useTournament } from "@/hooks/use-tournament";
import { isPlayed } from "@/lib/standings";
import type { LeagueMatch } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useTournamentStore } from "@/store/tournament-store";

function MatchRow({ match }: { match: LeagueMatch }) {
  const teams = useTeamMap();
  const setLeagueScore = useTournamentStore((state) => state.setLeagueScore);

  const home = teams.get(match.homeId);
  const away = teams.get(match.awayId);
  const played = isPlayed(match);
  const homeWon = played && (match.homeGoals as number) > (match.awayGoals as number);
  const awayWon = played && (match.awayGoals as number) > (match.homeGoals as number);

  return (
    <li className="glass flex items-center gap-2 p-2.5 sm:gap-3 sm:p-3">
      <div
        className={cn(
          "flex min-w-0 flex-1 items-center justify-end gap-2 text-right",
          homeWon ? "text-foreground" : "text-foreground/75",
        )}
      >
        <span className="min-w-0 truncate text-sm font-medium sm:text-[15px]">{home?.name}</span>
        <TeamCrest team={home} size="sm" />
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        <ScoreInput
          value={match.homeGoals}
          onChange={(value) => setLeagueScore(match.id, "home", value)}
          label={`Buts de ${home?.name ?? "l'équipe à domicile"}`}
          className={homeWon ? "border-mint/45 text-mint" : undefined}
        />
        <span aria-hidden className="text-xs text-muted-foreground">
          :
        </span>
        <ScoreInput
          value={match.awayGoals}
          onChange={(value) => setLeagueScore(match.id, "away", value)}
          label={`Buts de ${away?.name ?? "l'équipe à l'extérieur"}`}
          className={awayWon ? "border-mint/45 text-mint" : undefined}
        />
      </div>

      <div
        className={cn(
          "flex min-w-0 flex-1 items-center gap-2",
          awayWon ? "text-foreground" : "text-foreground/75",
        )}
      >
        <TeamCrest team={away} size="sm" />
        <span className="min-w-0 truncate text-sm font-medium sm:text-[15px]">{away?.name}</span>
      </div>
    </li>
  );
}

export function LeagueResults() {
  const tournament = useTournament();

  const matchdays = useMemo(() => {
    const map = new Map<number, LeagueMatch[]>();
    for (const match of tournament?.league.matches ?? []) {
      map.set(match.matchday, [...(map.get(match.matchday) ?? []), match]);
    }
    return [...map.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([matchday, matches]) => ({
        matchday,
        matches: matches.sort((a, b) => a.order - b.order),
      }));
  }, [tournament]);

  if (!tournament) return null;

  return (
    <div className="space-y-8">
      {matchdays.map(({ matchday, matches }, index) => {
        const done = matches.filter(isPlayed).length;

        return (
          <motion.section
            key={matchday}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(index * 0.03, 0.2), duration: 0.35 }}
            aria-labelledby={`matchday-${matchday}`}
          >
            <div className="mb-3 flex items-baseline justify-between gap-3">
              <h3 id={`matchday-${matchday}`} className="font-display text-base font-bold tracking-tight">
                Journée {matchday}
              </h3>
              <p className="tabular text-xs text-muted-foreground">
                {done} / {matches.length} joués
              </p>
            </div>

            <ul className="grid gap-2">
              {matches.map((match) => (
                <MatchRow key={match.id} match={match} />
              ))}
            </ul>
          </motion.section>
        );
      })}
    </div>
  );
}
