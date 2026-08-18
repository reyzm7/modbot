"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import {
  assignPots,
  bracketSizeFor,
  defaultMatchesPerTeam,
  generateLeagueSchedule,
  potCountFor,
  validateSchedule,
} from "@/lib/draw";
import { buildKnockoutRounds, drawKnockoutRound, syncKnockoutRounds } from "@/lib/knockout";
import { computeStandings, isLeagueComplete } from "@/lib/standings";
import type { Awards, Team, Tournament } from "@/lib/types";
import { clampInt, createId } from "@/lib/utils";

export const STORAGE_KEY = "ucl-tournament-manager-v1";

export type DrawResult = { ok: boolean; issues: string[] };

type TournamentState = {
  tournament: Tournament | null;
  hydrated: boolean;
};

type TournamentActions = {
  setHydrated: (value: boolean) => void;
  createTournament: (input: {
    name: string;
    logo?: string;
    teamCount: number;
    matchesPerTeam?: number;
  }) => void;
  updateIdentity: (patch: { name?: string; logo?: string | null }) => void;
  setTeamCount: (teamCount: number) => void;
  setMatchesPerTeam: (matchesPerTeam: number) => void;
  updateTeam: (teamId: string, patch: Partial<Pick<Team, "name" | "logo">>) => void;
  clearTeamLogo: (teamId: string) => void;
  runDraw: () => DrawResult;
  revealNext: () => void;
  revealAll: () => void;
  resetDraw: () => void;
  setLeagueScore: (matchId: string, side: "home" | "away", value: number | null) => void;
  clearLeagueScores: () => void;
  lockQualification: () => boolean;
  drawKnockout: (roundIndex: number) => void;
  setKnockoutScore: (
    matchId: string,
    field: "homeGoals" | "awayGoals" | "homePens" | "awayPens",
    value: number | null,
  ) => number;
  resetKnockout: () => void;
  setAward: (key: keyof Awards, value: string) => void;
  loadTournament: (tournament: Tournament) => void;
  resetTournament: () => void;
};

export type TournamentStore = TournamentState & TournamentActions;

function emptyTeam(index: number): Team {
  return { id: createId("team"), name: "", seed: index + 1, pot: 1 };
}

function resizeTeams(teams: Team[], teamCount: number): Team[] {
  const next = teams.slice(0, teamCount);
  while (next.length < teamCount) next.push(emptyTeam(next.length));
  return next;
}

/** Every mutation flows through here so pots, bracket size and time stay in sync. */
function refresh(tournament: Tournament): Tournament {
  const potCount = potCountFor(tournament.teams.length);
  return {
    ...tournament,
    potCount,
    teams: assignPots(tournament.teams, potCount),
    bracketSize: bracketSizeFor(tournament.teams.length),
    updatedAt: Date.now(),
  };
}

/** localStorage can be full or blocked; the app must survive that. */
const safeStorage = createJSONStorage(() => ({
  getItem: (name: string) => {
    try {
      return globalThis.localStorage?.getItem(name) ?? null;
    } catch {
      return null;
    }
  },
  setItem: (name: string, value: string) => {
    try {
      globalThis.localStorage?.setItem(name, value);
    } catch {
      /* quota exceeded or storage disabled: the session simply stays in memory */
    }
  },
  removeItem: (name: string) => {
    try {
      globalThis.localStorage?.removeItem(name);
    } catch {
      /* nothing to do */
    }
  },
}));

export const useTournamentStore = create<TournamentStore>()(
  persist(
    (set, get) => ({
      tournament: null,
      hydrated: false,

      setHydrated: (value) => set({ hydrated: value }),

      createTournament: ({ name, logo, teamCount, matchesPerTeam }) => {
        const size = clampInt(teamCount, 8, 36);
        const evenSize = size % 2 === 0 ? size : size + 1;
        const teams = resizeTeams([], evenSize);
        const now = Date.now();

        set({
          tournament: refresh({
            id: createId("tour"),
            name,
            logo: logo || undefined,
            createdAt: now,
            updatedAt: now,
            teams,
            matchesPerTeam: matchesPerTeam ?? defaultMatchesPerTeam(evenSize),
            potCount: potCountFor(evenSize),
            league: { drawn: false, revealed: 0, matches: [] },
            bracketSize: bracketSizeFor(evenSize),
            qualifiedSnapshot: null,
            knockout: [],
            awards: { mvp: "", topScorer: "", topAssister: "", topKeeper: "" },
          }),
        });
      },

      updateIdentity: (patch) => {
        const tournament = get().tournament;
        if (!tournament) return;
        set({
          tournament: refresh({
            ...tournament,
            name: patch.name !== undefined ? patch.name : tournament.name,
            logo: patch.logo === null ? undefined : patch.logo ?? tournament.logo,
          }),
        });
      },

      setTeamCount: (teamCount) => {
        const tournament = get().tournament;
        if (!tournament || tournament.league.drawn) return;

        const size = clampInt(teamCount, 8, 36);
        const evenSize = size % 2 === 0 ? size : size + 1;
        const teams = resizeTeams(tournament.teams, evenSize);
        const allowedMax = Math.min(12, evenSize - 1);
        const matchesPerTeam =
          tournament.matchesPerTeam > allowedMax
            ? defaultMatchesPerTeam(evenSize)
            : tournament.matchesPerTeam;

        set({ tournament: refresh({ ...tournament, teams, matchesPerTeam }) });
      },

      setMatchesPerTeam: (matchesPerTeam) => {
        const tournament = get().tournament;
        if (!tournament || tournament.league.drawn) return;
        set({ tournament: refresh({ ...tournament, matchesPerTeam }) });
      },

      updateTeam: (teamId, patch) => {
        const tournament = get().tournament;
        if (!tournament) return;
        set({
          tournament: refresh({
            ...tournament,
            teams: tournament.teams.map((team) =>
              team.id === teamId ? { ...team, ...patch } : team,
            ),
          }),
        });
      },

      clearTeamLogo: (teamId) => {
        const tournament = get().tournament;
        if (!tournament) return;
        set({
          tournament: refresh({
            ...tournament,
            teams: tournament.teams.map((team) =>
              team.id === teamId ? { ...team, logo: undefined } : team,
            ),
          }),
        });
      },

      runDraw: () => {
        const tournament = get().tournament;
        if (!tournament) return { ok: false, issues: ["Aucun tournoi en cours."] };

        const named = tournament.teams.filter((team) => team.name.trim().length > 0);
        if (named.length !== tournament.teams.length) {
          return { ok: false, issues: ["Toutes les équipes doivent être nommées."] };
        }

        try {
          const matches = generateLeagueSchedule(
            tournament.teams,
            tournament.matchesPerTeam,
            tournament.potCount,
          );
          const issues = validateSchedule(matches, tournament.teams, tournament.matchesPerTeam);
          if (issues.length > 0) return { ok: false, issues };

          set({
            tournament: refresh({
              ...tournament,
              league: { drawn: true, revealed: 0, matches },
              qualifiedSnapshot: null,
              knockout: [],
            }),
          });
          return { ok: true, issues: [] };
        } catch (error) {
          return {
            ok: false,
            issues: [error instanceof Error ? error.message : "Le tirage a échoué."],
          };
        }
      },

      revealNext: () => {
        const tournament = get().tournament;
        if (!tournament || !tournament.league.drawn) return;
        const revealed = Math.min(tournament.league.revealed + 1, tournament.league.matches.length);
        set({
          tournament: refresh({
            ...tournament,
            league: {
              ...tournament.league,
              revealed,
              matches: tournament.league.matches.map((match) =>
                match.order < revealed ? { ...match, revealed: true } : match,
              ),
            },
          }),
        });
      },

      revealAll: () => {
        const tournament = get().tournament;
        if (!tournament || !tournament.league.drawn) return;
        set({
          tournament: refresh({
            ...tournament,
            league: {
              ...tournament.league,
              revealed: tournament.league.matches.length,
              matches: tournament.league.matches.map((match) => ({ ...match, revealed: true })),
            },
          }),
        });
      },

      resetDraw: () => {
        const tournament = get().tournament;
        if (!tournament) return;
        set({
          tournament: refresh({
            ...tournament,
            league: { drawn: false, revealed: 0, matches: [] },
            qualifiedSnapshot: null,
            knockout: [],
          }),
        });
      },

      setLeagueScore: (matchId, side, value) => {
        const tournament = get().tournament;
        if (!tournament) return;
        const key = side === "home" ? "homeGoals" : "awayGoals";
        set({
          tournament: refresh({
            ...tournament,
            league: {
              ...tournament.league,
              matches: tournament.league.matches.map((match) =>
                match.id === matchId ? { ...match, [key]: value } : match,
              ),
            },
          }),
        });
      },

      clearLeagueScores: () => {
        const tournament = get().tournament;
        if (!tournament) return;
        set({
          tournament: refresh({
            ...tournament,
            league: {
              ...tournament.league,
              matches: tournament.league.matches.map((match) => ({
                ...match,
                homeGoals: null,
                awayGoals: null,
              })),
            },
          }),
        });
      },

      lockQualification: () => {
        const tournament = get().tournament;
        if (!tournament || !isLeagueComplete(tournament.league.matches)) return false;

        const standings = computeStandings(tournament.teams, tournament.league.matches);
        set({
          tournament: refresh({
            ...tournament,
            qualifiedSnapshot: standings.map((row) => row.teamId),
            knockout: buildKnockoutRounds(tournament.bracketSize),
          }),
        });
        return true;
      },

      drawKnockout: (roundIndex) => {
        const tournament = get().tournament;
        if (!tournament || !tournament.qualifiedSnapshot) return;

        const drawn = drawKnockoutRound(
          tournament.knockout,
          roundIndex,
          tournament.qualifiedSnapshot,
          tournament.bracketSize,
        );
        set({ tournament: refresh({ ...tournament, knockout: drawn }) });
      },

      setKnockoutScore: (matchId, field, value) => {
        const tournament = get().tournament;
        if (!tournament) return 0;

        const updated = tournament.knockout.map((round) => ({
          ...round,
          matches: round.matches.map((match) =>
            match.id === matchId ? { ...match, [field]: value } : match,
          ),
        }));

        const { rounds, resets } = syncKnockoutRounds(updated);
        set({ tournament: refresh({ ...tournament, knockout: rounds }) });
        return resets;
      },

      resetKnockout: () => {
        const tournament = get().tournament;
        if (!tournament) return;
        set({
          tournament: refresh({ ...tournament, qualifiedSnapshot: null, knockout: [] }),
        });
      },

      setAward: (key, value) => {
        const tournament = get().tournament;
        if (!tournament) return;
        set({
          tournament: refresh({ ...tournament, awards: { ...tournament.awards, [key]: value } }),
        });
      },

      loadTournament: (tournament) => set({ tournament: refresh(tournament) }),

      resetTournament: () => set({ tournament: null }),
    }),
    {
      name: STORAGE_KEY,
      version: 1,
      storage: safeStorage,
      // Hydrate manually so the first client render matches the server HTML.
      skipHydration: true,
      partialize: (state) => ({ tournament: state.tournament }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true);
      },
    },
  ),
);
