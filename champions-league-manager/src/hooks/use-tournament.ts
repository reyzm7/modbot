"use client";

import { useMemo } from "react";

import { tournamentChampion } from "@/lib/knockout";
import { computeStandings, isLeagueComplete } from "@/lib/standings";
import type { StepId } from "@/lib/steps";
import type { StandingRow, Team, Tournament } from "@/lib/types";
import { useTournamentStore } from "@/store/tournament-store";

export function useTournament(): Tournament | null {
  return useTournamentStore((state) => state.tournament);
}

export function useHydrated(): boolean {
  return useTournamentStore((state) => state.hydrated);
}

export function useTeamMap(): Map<string, Team> {
  const tournament = useTournament();
  return useMemo(
    () => new Map((tournament?.teams ?? []).map((team) => [team.id, team])),
    [tournament],
  );
}

export function useStandings(): StandingRow[] {
  const tournament = useTournament();
  return useMemo(
    () => (tournament ? computeStandings(tournament.teams, tournament.league.matches) : []),
    [tournament],
  );
}

export type StepAccess = Record<StepId, boolean>;

/** A step opens only once the previous one has produced the data it needs. */
export function useStepAccess(): StepAccess {
  const tournament = useTournament();

  return useMemo(() => {
    if (!tournament) {
      return {
        setup: true,
        draw: false,
        league: false,
        qualification: false,
        knockout: false,
        champion: false,
      };
    }

    const teamsReady =
      tournament.teams.length >= 8 && tournament.teams.every((team) => team.name.trim().length > 0);
    const drawReady = tournament.league.drawn && tournament.league.matches.length > 0;
    const revealed = drawReady && tournament.league.revealed >= tournament.league.matches.length;
    const leagueDone = isLeagueComplete(tournament.league.matches);
    const knockoutReady = Boolean(tournament.qualifiedSnapshot) && tournament.knockout.length > 0;
    const crowned = knockoutReady && Boolean(tournamentChampion(tournament.knockout));

    return {
      setup: true,
      draw: teamsReady,
      league: revealed,
      qualification: revealed && leagueDone,
      knockout: knockoutReady,
      champion: crowned,
    };
  }, [tournament]);
}

export function useLeagueProgress() {
  const tournament = useTournament();

  return useMemo(() => {
    const matches = tournament?.league.matches ?? [];
    const played = matches.filter(
      (match) => match.homeGoals !== null && match.awayGoals !== null,
    ).length;
    return {
      played,
      total: matches.length,
      percent: matches.length ? (played / matches.length) * 100 : 0,
      complete: matches.length > 0 && played === matches.length,
    };
  }, [tournament]);
}
