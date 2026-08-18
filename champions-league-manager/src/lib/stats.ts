import { knockoutWinner } from "@/lib/knockout";
import { computeStandings, isPlayed } from "@/lib/standings";
import type { StandingRow, Tournament } from "@/lib/types";
import { formatSigned } from "@/lib/utils";

export type BiggestWin = {
  winnerId: string;
  loserId: string;
  winnerGoals: number;
  loserGoals: number;
  margin: number;
  stage: string;
};

export type TournamentStats = {
  matchesPlayed: number;
  matchesTotal: number;
  totalGoals: number;
  averageGoals: number;
  biggestWin: BiggestWin | null;
  bestAttack: { teamId: string; value: number } | null;
  bestDefense: { teamId: string; value: number } | null;
  cleanSheets: { teamId: string; value: number } | null;
  standings: StandingRow[];
};

type FlatMatch = {
  homeId: string;
  awayId: string;
  homeGoals: number;
  awayGoals: number;
  stage: string;
};

export function flattenPlayedMatches(tournament: Tournament): FlatMatch[] {
  const flat: FlatMatch[] = [];

  for (const match of tournament.league.matches) {
    if (!isPlayed(match)) continue;
    flat.push({
      homeId: match.homeId,
      awayId: match.awayId,
      homeGoals: match.homeGoals as number,
      awayGoals: match.awayGoals as number,
      stage: `Journée ${match.matchday}`,
    });
  }

  for (const round of tournament.knockout) {
    for (const match of round.matches) {
      if (!match.homeId || !match.awayId) continue;
      if (match.homeGoals === null || match.awayGoals === null) continue;
      flat.push({
        homeId: match.homeId,
        awayId: match.awayId,
        homeGoals: match.homeGoals,
        awayGoals: match.awayGoals,
        stage: round.name,
      });
    }
  }

  return flat;
}

export function computeStats(tournament: Tournament): TournamentStats {
  const standings = computeStandings(tournament.teams, tournament.league.matches);
  const played = flattenPlayedMatches(tournament);

  const totalGoals = played.reduce((sum, match) => sum + match.homeGoals + match.awayGoals, 0);

  let biggestWin: BiggestWin | null = null;
  for (const match of played) {
    const margin = Math.abs(match.homeGoals - match.awayGoals);
    if (margin === 0) continue;
    if (!biggestWin || margin > biggestWin.margin) {
      const homeWon = match.homeGoals > match.awayGoals;
      biggestWin = {
        winnerId: homeWon ? match.homeId : match.awayId,
        loserId: homeWon ? match.awayId : match.homeId,
        winnerGoals: homeWon ? match.homeGoals : match.awayGoals,
        loserGoals: homeWon ? match.awayGoals : match.homeGoals,
        margin,
        stage: match.stage,
      };
    }
  }

  // Attack and defence come from the league phase alone: every club plays the
  // same number of games there, so the comparison is actually fair.
  const ranked = standings.filter((row) => row.played > 0);
  const bestAttack = ranked.length
    ? ranked.reduce((best, row) => (row.goalsFor > best.goalsFor ? row : best))
    : null;
  const bestDefense = ranked.length
    ? ranked.reduce((best, row) => (row.goalsAgainst < best.goalsAgainst ? row : best))
    : null;

  const cleanSheetCount = new Map<string, number>();
  for (const match of tournament.league.matches) {
    if (!isPlayed(match)) continue;
    if (match.awayGoals === 0) {
      cleanSheetCount.set(match.homeId, (cleanSheetCount.get(match.homeId) ?? 0) + 1);
    }
    if (match.homeGoals === 0) {
      cleanSheetCount.set(match.awayId, (cleanSheetCount.get(match.awayId) ?? 0) + 1);
    }
  }

  let cleanSheets: { teamId: string; value: number } | null = null;
  for (const [teamId, value] of cleanSheetCount) {
    if (!cleanSheets || value > cleanSheets.value) cleanSheets = { teamId, value };
  }

  const knockoutTotal = tournament.knockout.reduce((sum, round) => sum + round.matches.length, 0);

  return {
    matchesPlayed: played.length,
    matchesTotal: tournament.league.matches.length + knockoutTotal,
    totalGoals,
    averageGoals: played.length ? totalGoals / played.length : 0,
    biggestWin,
    bestAttack: bestAttack ? { teamId: bestAttack.teamId, value: bestAttack.goalsFor } : null,
    bestDefense: bestDefense ? { teamId: bestDefense.teamId, value: bestDefense.goalsAgainst } : null,
    cleanSheets,
    standings,
  };
}

/** How far each club went, used for the final recap. */
export function eliminationStage(tournament: Tournament, teamId: string): string | null {
  for (let index = tournament.knockout.length - 1; index >= 0; index -= 1) {
    const round = tournament.knockout[index];
    for (const match of round.matches) {
      if (match.homeId !== teamId && match.awayId !== teamId) continue;
      const winner = knockoutWinner(match);
      if (winner && winner !== teamId) return round.name;
    }
  }
  return null;
}

export type TeamAward = {
  key: string;
  label: string;
  caption: string;
  teamId: string;
  value: string;
  /** "honour" pour les distinctions flatteuses, "wooden" pour les contre-performances. */
  tone: "honour" | "wooden";
};

/**
 * Palmarès collectif, entièrement déduit des résultats. Tout est mesuré sur la
 * phase de ligue : chaque club y dispute le même nombre de matchs, donc la
 * comparaison est équitable — ce qui ne serait pas le cas en incluant le
 * tableau final, où un finaliste joue bien plus qu'un éliminé des barrages.
 */
export function computeTeamAwards(tournament: Tournament): TeamAward[] {
  const standings = computeStandings(tournament.teams, tournament.league.matches);
  const played = tournament.league.matches.filter(isPlayed);
  if (played.length === 0 || standings.length === 0) return [];

  const awards: TeamAward[] = [];
  const byGoalsFor = [...standings].sort((a, b) => b.goalsFor - a.goalsFor);
  const byGoalsAgainst = [...standings].sort((a, b) => a.goalsAgainst - b.goalsAgainst);
  const byWins = [...standings].sort((a, b) => b.wins - a.wins);
  const byDiff = [...standings].sort((a, b) => b.goalDiff - a.goalDiff);

  if (byGoalsFor[0]) {
    awards.push({
      key: "attack",
      tone: "honour",
      label: "Meilleure attaque",
      caption: "Le plus de buts marqués",
      teamId: byGoalsFor[0].teamId,
      value: `${byGoalsFor[0].goalsFor} buts`,
    });
  }

  if (byGoalsAgainst[0]) {
    awards.push({
      key: "defense",
      tone: "honour",
      label: "Meilleure défense",
      caption: "Le moins de buts encaissés",
      teamId: byGoalsAgainst[0].teamId,
      value: `${byGoalsAgainst[0].goalsAgainst} encaissés`,
    });
  }

  if (byWins[0]) {
    awards.push({
      key: "wins",
      tone: "honour",
      label: "Le plus de victoires",
      caption: "La régularité récompensée",
      teamId: byWins[0].teamId,
      value: `${byWins[0].wins} victoires`,
    });
  }

  if (byDiff[0]) {
    awards.push({
      key: "diff",
      tone: "honour",
      label: "Meilleure différence",
      caption: "L'écart le plus large",
      teamId: byDiff[0].teamId,
      value: formatSigned(byDiff[0].goalDiff),
    });
  }

  // Séries : calculées sur l'ordre des journées, pas sur l'ordre de saisie.
  const ordered = [...played].sort((a, b) => a.matchday - b.matchday || a.order - b.order);
  const streak = new Map<string, number>();
  const best = new Map<string, number>();
  const cleanSheets = new Map<string, number>();

  for (const match of ordered) {
    const home = match.homeGoals as number;
    const away = match.awayGoals as number;

    for (const [teamId, won] of [
      [match.homeId, home > away],
      [match.awayId, away > home],
    ] as const) {
      const next = won ? (streak.get(teamId) ?? 0) + 1 : 0;
      streak.set(teamId, next);
      best.set(teamId, Math.max(best.get(teamId) ?? 0, next));
    }

    if (away === 0) cleanSheets.set(match.homeId, (cleanSheets.get(match.homeId) ?? 0) + 1);
    if (home === 0) cleanSheets.set(match.awayId, (cleanSheets.get(match.awayId) ?? 0) + 1);
  }

  const bestStreak = [...best.entries()].sort((a, b) => b[1] - a[1])[0];
  if (bestStreak && bestStreak[1] > 1) {
    awards.push({
      key: "streak",
      tone: "honour",
      label: "Meilleure série",
      caption: "Victoires consécutives",
      teamId: bestStreak[0],
      value: `${bestStreak[1]} d'affilée`,
    });
  }

  const bestClean = [...cleanSheets.entries()].sort((a, b) => b[1] - a[1])[0];
  if (bestClean && bestClean[1] > 0) {
    awards.push({
      key: "clean",
      tone: "honour",
      label: "Le plus de clean sheets",
      caption: "Matchs sans encaisser",
      teamId: bestClean[0],
      value: `${bestClean[1]} match${bestClean[1] > 1 ? "s" : ""}`,
    });
  }

  // Le revers de la médaille : ce sont souvent les chiffres les plus commentés.
  const worstAttack = [...standings].sort((a, b) => a.goalsFor - b.goalsFor)[0];
  if (worstAttack) {
    awards.push({
      key: "worst-attack",
      tone: "wooden",
      label: "Attaque la plus timide",
      caption: "Le moins de buts marqués",
      teamId: worstAttack.teamId,
      value: `${worstAttack.goalsFor} buts`,
    });
  }

  const worstDefense = [...standings].sort((a, b) => b.goalsAgainst - a.goalsAgainst)[0];
  if (worstDefense) {
    awards.push({
      key: "worst-defense",
      tone: "wooden",
      label: "Défense la plus généreuse",
      caption: "Le plus de buts encaissés",
      teamId: worstDefense.teamId,
      value: `${worstDefense.goalsAgainst} encaissés`,
    });
  }

  const mostDraws = [...standings].sort((a, b) => b.draws - a.draws)[0];
  if (mostDraws && mostDraws.draws > 1) {
    awards.push({
      key: "draws",
      tone: "wooden",
      label: "Le roi du match nul",
      caption: "Le plus de matchs partagés",
      teamId: mostDraws.teamId,
      value: `${mostDraws.draws} nuls`,
    });
  }

  // Spectacle : le club dont les matchs ont produit le plus de buts, tous camps confondus.
  const involved = new Map<string, number>();
  for (const match of played) {
    const total = (match.homeGoals as number) + (match.awayGoals as number);
    involved.set(match.homeId, (involved.get(match.homeId) ?? 0) + total);
    involved.set(match.awayId, (involved.get(match.awayId) ?? 0) + total);
  }
  const mostSpectacle = [...involved.entries()].sort((a, b) => b[1] - a[1])[0];
  if (mostSpectacle && mostSpectacle[1] > 0) {
    awards.push({
      key: "spectacle",
      tone: "honour",
      label: "Le plus spectaculaire",
      caption: "Le plus de buts dans ses matchs",
      teamId: mostSpectacle[0],
      value: `${mostSpectacle[1]} buts`,
    });
  }

  return awards;
}
