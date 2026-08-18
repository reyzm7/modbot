import type { LeagueMatch, Team } from "@/lib/types";
import { createId, shuffle } from "@/lib/utils";

export const MIN_TEAMS = 8;
export const MAX_TEAMS = 36;

/** Pots only make sense when the field splits evenly. */
export function potCountFor(teamCount: number): number {
  if (teamCount % 4 === 0 && teamCount >= 8) return 4;
  if (teamCount % 2 === 0) return 2;
  return 1;
}

/** A team plays one match per matchday, so the count is even and below the field size. */
export function allowedMatchCounts(teamCount: number): number[] {
  const max = Math.min(12, teamCount - 1);
  const counts: number[] = [];
  for (let value = 2; value <= max; value += 2) counts.push(value);
  return counts;
}

export function defaultMatchesPerTeam(teamCount: number): number {
  const counts = allowedMatchCounts(teamCount);
  if (counts.includes(8)) return 8;
  return counts[counts.length - 1] ?? 2;
}

/**
 * Largest power of two K such that the field can supply K/2 direct qualifiers
 * plus K play-off entrants (the UEFA 8 + 16 shape, generalised).
 */
export function bracketSizeFor(teamCount: number): number {
  let candidate = 2;
  let best = 0;
  while (candidate * 1.5 <= teamCount) {
    best = candidate;
    candidate *= 2;
  }
  return best;
}

export function assignPots(teams: Team[], potCount: number): Team[] {
  const perPot = Math.ceil(teams.length / potCount);
  return teams.map((team, index) => ({
    ...team,
    seed: index + 1,
    pot: Math.min(potCount, Math.floor(index / perPot) + 1),
  }));
}

/**
 * Circle method: a 1-factorization of the complete graph on `size` vertices.
 * Returns size-1 rounds; every round is a perfect matching and every pair
 * appears exactly once across the whole set.
 */
function roundRobinRounds(size: number): Array<Array<[number, number]>> {
  const positions = Array.from({ length: size }, (_, index) => index);
  const rounds: Array<Array<[number, number]>> = [];

  for (let round = 0; round < size - 1; round += 1) {
    const pairs: Array<[number, number]> = [];
    for (let i = 0; i < size / 2; i += 1) {
      pairs.push([positions[i], positions[size - 1 - i]]);
    }
    rounds.push(pairs);

    const fixed = positions[0];
    const rotating = positions.slice(1);
    rotating.unshift(rotating.pop() as number);
    positions.splice(0, size, fixed, ...rotating);
  }

  return rounds;
}

/** Squared deviation from "the same number of opponents from every pot". */
function potPenalty(counts: number[][], potCount: number, target: number): number {
  let penalty = 0;
  for (const row of counts) {
    for (let pot = 1; pot <= potCount; pot += 1) {
      penalty += (row[pot] - target) ** 2;
    }
  }
  return penalty;
}

function emptyCounts(teamCount: number, potCount: number): number[][] {
  return Array.from({ length: teamCount }, () => new Array<number>(potCount + 1).fill(0));
}

function applyRound(
  counts: number[][],
  pairs: Array<[number, number]>,
  pots: number[],
  sign: 1 | -1,
) {
  for (const [a, b] of pairs) {
    counts[a][pots[b]] += sign;
    counts[b][pots[a]] += sign;
  }
}

/**
 * Splits circle-method positions into pot classes. Because the pivot position
 * and the rotating ones follow a fixed arithmetic pattern, aligning pots to
 * these classes lets far more teams reach the exact "same number of opponents
 * from every pot" target than a random labelling ever would.
 */
function potPositionClasses(teamCount: number, potCount: number): number[][] {
  const perPot = teamCount / potCount;
  const buckets: number[][] = Array.from({ length: potCount }, () => []);
  buckets[potCount - 1].push(0);
  for (let position = 1; position < teamCount; position += 1) {
    buckets[(position - 1) % potCount].push(position);
  }

  for (let index = 0; index < potCount; index += 1) {
    while (buckets[index].length > perPot) {
      const target = buckets.findIndex((bucket) => bucket.length < perPot);
      if (target === -1) break;
      buckets[target].push(buckets[index].pop() as number);
    }
  }

  return buckets;
}

/** Randomises which club sits on which position, without leaving its pot class. */
function mapTeamsToPositions(
  pots: number[],
  buckets: number[][],
  teamCount: number,
  potCount: number,
): number[] {
  const teamsByPot: number[][] = Array.from({ length: potCount }, () => []);
  pots.forEach((pot, index) => teamsByPot[pot - 1].push(index));

  const aligned = buckets.every((bucket, index) => bucket.length === teamsByPot[index].length);
  if (!aligned) {
    return shuffle(Array.from({ length: teamCount }, (_, index) => index));
  }

  const positionToTeam = new Array<number>(teamCount);
  buckets.forEach((bucket, index) => {
    const clubs = shuffle(teamsByPot[index]);
    bucket.forEach((position, slot) => {
      positionToTeam[position] = clubs[slot];
    });
  });

  return positionToTeam;
}

/**
 * Picks `matchesPerTeam` matchdays out of the full 1-factorization, greedily
 * then by swapping, so every team faces a similar number of opponents from
 * each pot. Any selection is already duplicate-free; this only tunes fairness.
 */
function selectMatchdays(
  allRounds: Array<Array<[number, number]>>,
  pots: number[],
  potCount: number,
  matchesPerTeam: number,
  teamCount: number,
): { rounds: Array<Array<[number, number]>>; penalty: number } {
  const target = matchesPerTeam / potCount;
  const counts = emptyCounts(teamCount, potCount);
  const remaining = new Set<number>(allRounds.map((_, index) => index));
  const chosen: number[] = [];

  for (let pick = 0; pick < matchesPerTeam; pick += 1) {
    let bestIndex = -1;
    let bestPenalty = Number.POSITIVE_INFINITY;

    for (const index of shuffle([...remaining])) {
      applyRound(counts, allRounds[index], pots, 1);
      const penalty = potPenalty(counts, potCount, target);
      applyRound(counts, allRounds[index], pots, -1);
      if (penalty < bestPenalty) {
        bestPenalty = penalty;
        bestIndex = index;
      }
    }

    applyRound(counts, allRounds[bestIndex], pots, 1);
    remaining.delete(bestIndex);
    chosen.push(bestIndex);
  }

  let penalty = potPenalty(counts, potCount, target);

  for (let pass = 0; pass < 12 && penalty > 0; pass += 1) {
    let improved = false;

    for (let slot = 0; slot < chosen.length; slot += 1) {
      const current = chosen[slot];
      applyRound(counts, allRounds[current], pots, -1);

      let bestIndex = current;
      let bestPenalty = penalty;

      for (const candidate of shuffle([...remaining])) {
        applyRound(counts, allRounds[candidate], pots, 1);
        const next = potPenalty(counts, potCount, target);
        applyRound(counts, allRounds[candidate], pots, -1);
        if (next < bestPenalty) {
          bestPenalty = next;
          bestIndex = candidate;
        }
      }

      applyRound(counts, allRounds[bestIndex], pots, 1);
      if (bestIndex !== current) {
        remaining.delete(bestIndex);
        remaining.add(current);
        chosen[slot] = bestIndex;
        penalty = bestPenalty;
        improved = true;
      }
    }

    if (!improved) break;
  }

  return { rounds: chosen.map((index) => allRounds[index]), penalty };
}

/**
 * Orients every fixture along an Eulerian circuit. Each team has an even
 * number of matches, so in-degree equals out-degree: every club gets exactly
 * half of its games at home. No heuristics, no drift.
 */
function orientHomeAway(
  edges: Array<[number, number]>,
  teamCount: number,
): Array<[number, number]> {
  const adjacency: number[][] = Array.from({ length: teamCount }, () => []);
  edges.forEach(([a, b], index) => {
    adjacency[a].push(index);
    adjacency[b].push(index);
  });
  for (let vertex = 0; vertex < teamCount; vertex += 1) {
    adjacency[vertex] = shuffle(adjacency[vertex]);
  }

  const used = new Array<boolean>(edges.length).fill(false);
  const cursor = new Array<number>(teamCount).fill(0);
  const oriented = new Array<[number, number]>(edges.length);
  const starts = shuffle(Array.from({ length: teamCount }, (_, index) => index));

  for (const start of starts) {
    if (cursor[start] >= adjacency[start].length) continue;
    const stack: number[] = [start];

    while (stack.length > 0) {
      const vertex = stack[stack.length - 1];
      while (cursor[vertex] < adjacency[vertex].length && used[adjacency[vertex][cursor[vertex]]]) {
        cursor[vertex] += 1;
      }
      if (cursor[vertex] >= adjacency[vertex].length) {
        stack.pop();
        continue;
      }

      const edgeIndex = adjacency[vertex][cursor[vertex]];
      used[edgeIndex] = true;
      const [a, b] = edges[edgeIndex];
      const next = a === vertex ? b : a;
      oriented[edgeIndex] = [vertex, next];
      stack.push(next);
    }
  }

  return oriented;
}

export type ScheduleIssue = string;

export function validateSchedule(
  matches: LeagueMatch[],
  teams: Team[],
  matchesPerTeam: number,
): ScheduleIssue[] {
  const issues: ScheduleIssue[] = [];
  const played = new Map<string, number>();
  const homeCount = new Map<string, number>();
  const pairs = new Set<string>();
  const perMatchday = new Map<number, Set<string>>();

  for (const team of teams) {
    played.set(team.id, 0);
    homeCount.set(team.id, 0);
  }

  for (const match of matches) {
    if (match.homeId === match.awayId) {
      issues.push("Une équipe s'affronte elle-même.");
    }

    const key = [match.homeId, match.awayId].sort().join("::");
    if (pairs.has(key)) issues.push("Une affiche est tirée deux fois.");
    pairs.add(key);

    played.set(match.homeId, (played.get(match.homeId) ?? 0) + 1);
    played.set(match.awayId, (played.get(match.awayId) ?? 0) + 1);
    homeCount.set(match.homeId, (homeCount.get(match.homeId) ?? 0) + 1);

    const day = perMatchday.get(match.matchday) ?? new Set<string>();
    if (day.has(match.homeId) || day.has(match.awayId)) {
      issues.push(`Une équipe joue deux fois lors de la journée ${match.matchday}.`);
    }
    day.add(match.homeId);
    day.add(match.awayId);
    perMatchday.set(match.matchday, day);
  }

  for (const team of teams) {
    if (played.get(team.id) !== matchesPerTeam) {
      issues.push(`${team.name} ne dispute pas ${matchesPerTeam} matchs.`);
    }
  }

  const homeValues = [...homeCount.values()];
  if (homeValues.length > 0 && Math.max(...homeValues) - Math.min(...homeValues) > 1) {
    issues.push("La répartition domicile / extérieur est déséquilibrée.");
  }

  return issues;
}

/**
 * Builds the whole league phase: every team plays `matchesPerTeam` different
 * opponents, one per matchday, half of them at home, with opponents spread
 * across the pots as evenly as the field allows.
 */
export function generateLeagueSchedule(
  teams: Team[],
  matchesPerTeam: number,
  potCount: number,
): LeagueMatch[] {
  const teamCount = teams.length;
  if (teamCount < MIN_TEAMS || teamCount % 2 !== 0) {
    throw new Error("Le tirage exige un nombre d'équipes pair.");
  }
  if (matchesPerTeam % 2 !== 0 || matchesPerTeam >= teamCount) {
    throw new Error("Le nombre de matchs par équipe est invalide.");
  }

  const pots = teams.map((team) => Math.min(potCount, Math.max(1, team.pot)));
  const positionBuckets = potPositionClasses(teamCount, potCount);
  let best: Array<Array<[number, number]>> | null = null;
  let bestPenalty = Number.POSITIVE_INFINITY;

  for (let attempt = 0; attempt < 8; attempt += 1) {
    const positionToTeam = mapTeamsToPositions(pots, positionBuckets, teamCount, potCount);
    const allRounds = roundRobinRounds(teamCount).map((pairs) =>
      pairs.map(([a, b]) => [positionToTeam[a], positionToTeam[b]] as [number, number]),
    );

    const { rounds, penalty } = selectMatchdays(
      allRounds,
      pots,
      potCount,
      matchesPerTeam,
      teamCount,
    );

    if (penalty < bestPenalty) {
      bestPenalty = penalty;
      best = rounds;
      if (penalty === 0) break;
    }
  }

  const selected = shuffle(best as Array<Array<[number, number]>>);
  const edges: Array<[number, number]> = [];
  const matchdayOf: number[] = [];

  selected.forEach((pairs, dayIndex) => {
    for (const pair of shuffle(pairs)) {
      edges.push(pair);
      matchdayOf.push(dayIndex + 1);
    }
  });

  const oriented = orientHomeAway(edges, teamCount);
  const matchesPerDay = teamCount / 2;
  const counters = new Map<number, number>();

  const matches: LeagueMatch[] = oriented.map(([home, away], index) => {
    const matchday = matchdayOf[index];
    const position = counters.get(matchday) ?? 0;
    counters.set(matchday, position + 1);

    return {
      id: createId("lm"),
      matchday,
      order: (matchday - 1) * matchesPerDay + position,
      homeId: teams[home].id,
      awayId: teams[away].id,
      homeGoals: null,
      awayGoals: null,
      revealed: false,
    };
  });

  return matches.sort((a, b) => a.order - b.order);
}
