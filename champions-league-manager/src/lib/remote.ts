import { isLeagueComplete } from "@/lib/standings";
import { tournamentChampion } from "@/lib/knockout";
import type { Tournament } from "@/lib/types";

export type TournamentStatus = "setup" | "draw" | "league" | "knockout" | "done";

export type TournamentSummary = {
  slug: string;
  name: string;
  logo: string | null;
  status: TournamentStatus;
  published: boolean;
  teamCount: number;
  playedMatches: number;
  totalMatches: number;
  updatedAt: string;
};

export const STATUS_LABEL: Record<TournamentStatus, string> = {
  setup: "En préparation",
  draw: "Tirage au sort",
  league: "Phase de ligue",
  knockout: "Phase finale",
  done: "Terminé",
};

/** L'étape 1 est finie : c'est le déclencheur de la publication côté visiteurs. */
export function isSetupComplete(tournament: Tournament): boolean {
  return (
    tournament.name.trim().length >= 2 &&
    tournament.teams.length > 0 &&
    tournament.teams.every((team) => team.name.trim().length > 0)
  );
}

export function tournamentStatus(tournament: Tournament): TournamentStatus {
  if (!isSetupComplete(tournament)) return "setup";
  if (!tournament.league.drawn) return "draw";
  if (tournamentChampion(tournament.knockout)) return "done";
  if (tournament.qualifiedSnapshot) return "knockout";
  if (isLeagueComplete(tournament.league.matches)) return "knockout";
  return "league";
}

export function isPublished(tournament: Tournament): boolean {
  return isSetupComplete(tournament) && !tournament.hidden;
}
