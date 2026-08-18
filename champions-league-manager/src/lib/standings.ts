import type { LeagueMatch, QualificationBand, StandingRow, Team } from "@/lib/types";

export function isPlayed(match: { homeGoals: number | null; awayGoals: number | null }): boolean {
  return match.homeGoals !== null && match.awayGoals !== null;
}

export function playedCount(matches: LeagueMatch[]): number {
  return matches.filter(isPlayed).length;
}

export function isLeagueComplete(matches: LeagueMatch[]): boolean {
  return matches.length > 0 && matches.every(isPlayed);
}

/**
 * Live table. Ranking criteria, in order: points, goal difference, goals
 * scored, then club name so the order never flickers between renders.
 */
export function computeStandings(teams: Team[], matches: LeagueMatch[]): StandingRow[] {
  const rows = new Map<string, StandingRow>();

  for (const team of teams) {
    rows.set(team.id, {
      teamId: team.id,
      rank: 0,
      played: 0,
      wins: 0,
      draws: 0,
      losses: 0,
      goalsFor: 0,
      goalsAgainst: 0,
      goalDiff: 0,
      points: 0,
      form: [],
    });
  }

  const ordered = [...matches].sort((a, b) => a.order - b.order);

  for (const match of ordered) {
    if (!isPlayed(match)) continue;
    const home = rows.get(match.homeId);
    const away = rows.get(match.awayId);
    if (!home || !away) continue;

    const homeGoals = match.homeGoals as number;
    const awayGoals = match.awayGoals as number;

    home.played += 1;
    away.played += 1;
    home.goalsFor += homeGoals;
    home.goalsAgainst += awayGoals;
    away.goalsFor += awayGoals;
    away.goalsAgainst += homeGoals;

    if (homeGoals > awayGoals) {
      home.wins += 1;
      home.points += 3;
      away.losses += 1;
      home.form.push("W");
      away.form.push("L");
    } else if (homeGoals < awayGoals) {
      away.wins += 1;
      away.points += 3;
      home.losses += 1;
      home.form.push("L");
      away.form.push("W");
    } else {
      home.draws += 1;
      away.draws += 1;
      home.points += 1;
      away.points += 1;
      home.form.push("D");
      away.form.push("D");
    }
  }

  const names = new Map(teams.map((team) => [team.id, team.name]));

  const table = [...rows.values()].map((row) => ({
    ...row,
    goalDiff: row.goalsFor - row.goalsAgainst,
    form: row.form.slice(-5),
  }));

  table.sort((a, b) => {
    if (b.points !== a.points) return b.points - a.points;
    if (b.goalDiff !== a.goalDiff) return b.goalDiff - a.goalDiff;
    if (b.goalsFor !== a.goalsFor) return b.goalsFor - a.goalsFor;
    return (names.get(a.teamId) ?? "").localeCompare(names.get(b.teamId) ?? "", "fr");
  });

  return table.map((row, index) => ({ ...row, rank: index + 1 }));
}

export function qualificationBand(rank: number, bracketSize: number): QualificationBand {
  const direct = bracketSize / 2;
  if (rank <= direct) return "direct";
  if (rank <= direct + bracketSize) return "playoff";
  return "out";
}

export const BAND_LABEL: Record<QualificationBand, string> = {
  direct: "Qualifié directement",
  playoff: "Barrages",
  out: "Éliminé",
};

export const BAND_SHORT: Record<QualificationBand, string> = {
  direct: "Qualifié",
  playoff: "Barrages",
  out: "Éliminé",
};
