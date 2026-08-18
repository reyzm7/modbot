import type { KnockoutMatch, KnockoutRound, KnockoutRoundId, SlotSource } from "@/lib/types";
import { createId, shuffle } from "@/lib/utils";

export function roundIdForSize(size: number): KnockoutRoundId {
  if (size === 16) return "r16";
  if (size === 8) return "qf";
  if (size === 4) return "sf";
  return "final";
}

export function roundNameForSize(size: number): string {
  if (size === 16) return "Huitièmes de finale";
  if (size === 8) return "Quarts de finale";
  if (size === 4) return "Demi-finales";
  return "Finale";
}

/** Empty bracket: barrages, then every knockout round down to the final. */
export function buildKnockoutRounds(bracketSize: number): KnockoutRound[] {
  const rounds: KnockoutRound[] = [
    { id: "playoff", name: "Barrages", teamCount: bracketSize, drawn: false, matches: [] },
  ];

  for (let size = bracketSize; size >= 2; size /= 2) {
    rounds.push({
      id: roundIdForSize(size),
      name: roundNameForSize(size),
      teamCount: size,
      drawn: false,
      matches: [],
    });
  }

  return rounds;
}

export function knockoutWinner(match: KnockoutMatch | undefined | null): string | null {
  if (!match || !match.homeId || !match.awayId) return null;
  if (match.homeGoals === null || match.awayGoals === null) return null;
  if (match.homeGoals > match.awayGoals) return match.homeId;
  if (match.awayGoals > match.homeGoals) return match.awayId;
  if (match.homePens !== null && match.awayPens !== null && match.homePens !== match.awayPens) {
    return match.homePens > match.awayPens ? match.homeId : match.awayId;
  }
  return null;
}

export function knockoutLoser(match: KnockoutMatch | undefined | null): string | null {
  const winner = knockoutWinner(match);
  if (!winner || !match) return null;
  return winner === match.homeId ? match.awayId : match.homeId;
}

/** True once the 90 minutes are level and a shootout is required. */
export function needsShootout(match: KnockoutMatch): boolean {
  return (
    match.homeGoals !== null && match.awayGoals !== null && match.homeGoals === match.awayGoals
  );
}

export function isRoundComplete(round: KnockoutRound): boolean {
  return round.drawn && round.matches.length > 0 && round.matches.every((m) => knockoutWinner(m));
}

export function canDrawRound(rounds: KnockoutRound[], index: number): boolean {
  if (index < 0 || index >= rounds.length) return false;
  if (rounds[index].drawn) return false;
  if (index === 0) return true;
  if (index === 1) return isRoundComplete(rounds[0]);
  return isRoundComplete(rounds[index - 1]);
}

function makeMatch(
  roundId: KnockoutRoundId,
  order: number,
  home: { teamId: string | null; source: SlotSource | null },
  away: { teamId: string | null; source: SlotSource | null },
): KnockoutMatch {
  return {
    id: createId("km"),
    roundId,
    order,
    homeId: home.teamId,
    awayId: away.teamId,
    homeSource: home.source,
    awaySource: away.source,
    homeGoals: null,
    awayGoals: null,
    homePens: null,
    awayPens: null,
  };
}

/** Shuffles inside consecutive bands, the way seeded cup draws are handled. */
function shuffleBands<T>(items: T[], bandSize: number): T[] {
  const result: T[] = [];
  for (let start = 0; start < items.length; start += bandSize) {
    result.push(...shuffle(items.slice(start, start + bandSize)));
  }
  return result;
}

export function drawKnockoutRound(
  rounds: KnockoutRound[],
  index: number,
  snapshot: string[],
  bracketSize: number,
): KnockoutRound[] {
  const round = rounds[index];
  const rankOf = new Map(snapshot.map((teamId, position) => [teamId, position + 1]));
  const matches: KnockoutMatch[] = [];

  if (round.id === "playoff") {
    const directCount = bracketSize / 2;
    const pool = snapshot.slice(directCount, directCount + bracketSize);
    const seeded = shuffleBands(pool.slice(0, bracketSize / 2), 2);
    const unseeded = shuffleBands(pool.slice(bracketSize / 2), 2);

    for (let position = 0; position < seeded.length; position += 1) {
      const homeId = seeded[position];
      const awayId = unseeded[seeded.length - 1 - position];
      matches.push(
        makeMatch(
          round.id,
          position,
          { teamId: homeId, source: { type: "standing", rank: rankOf.get(homeId) ?? 0 } },
          { teamId: awayId, source: { type: "standing", rank: rankOf.get(awayId) ?? 0 } },
        ),
      );
    }
  } else if (index === 1) {
    const direct = snapshot.slice(0, bracketSize / 2);
    const qualifiers = shuffle(
      rounds[0].matches.map((match) => ({ matchId: match.id, teamId: knockoutWinner(match) })),
    );

    direct.forEach((homeId, position) => {
      const qualifier = qualifiers[position];
      matches.push(
        makeMatch(
          round.id,
          position,
          { teamId: homeId, source: { type: "standing", rank: rankOf.get(homeId) ?? 0 } },
          {
            teamId: qualifier?.teamId ?? null,
            source: qualifier ? { type: "match", matchId: qualifier.matchId } : null,
          },
        ),
      );
    });
  } else {
    const previous = shuffle(rounds[index - 1].matches);

    for (let position = 0; position * 2 + 1 < previous.length; position += 1) {
      const first = previous[position * 2];
      const second = previous[position * 2 + 1];
      const firstTeam = knockoutWinner(first);
      const secondTeam = knockoutWinner(second);

      // The better league-phase finisher hosts the tie.
      const firstRank = rankOf.get(firstTeam ?? "") ?? Number.MAX_SAFE_INTEGER;
      const secondRank = rankOf.get(secondTeam ?? "") ?? Number.MAX_SAFE_INTEGER;
      const flip = secondRank < firstRank;

      const homeMatch = flip ? second : first;
      const awayMatch = flip ? first : second;

      matches.push(
        makeMatch(
          round.id,
          position,
          {
            teamId: knockoutWinner(homeMatch),
            source: { type: "match", matchId: homeMatch.id },
          },
          {
            teamId: knockoutWinner(awayMatch),
            source: { type: "match", matchId: awayMatch.id },
          },
        ),
      );
    }
  }

  return rounds.map((item, position) =>
    position === index ? { ...item, drawn: true, matches } : item,
  );
}

/**
 * Re-resolves every slot that points at an earlier tie. Editing a result far
 * back in the bracket therefore rewrites the rest of the path, and any tie
 * whose participants changed has its score cleared instead of staying wrong.
 */
export function syncKnockoutRounds(rounds: KnockoutRound[]): {
  rounds: KnockoutRound[];
  resets: number;
} {
  const next = rounds.map((round) => ({
    ...round,
    matches: round.matches.map((match) => ({ ...match })),
  }));

  const byId = new Map<string, KnockoutMatch>();
  for (const round of next) {
    for (const match of round.matches) byId.set(match.id, match);
  }

  let resets = 0;

  for (const round of next) {
    for (const match of round.matches) {
      let changed = false;

      if (match.homeSource?.type === "match") {
        const winner = knockoutWinner(byId.get(match.homeSource.matchId));
        if (winner !== match.homeId) {
          match.homeId = winner;
          changed = true;
        }
      }

      if (match.awaySource?.type === "match") {
        const winner = knockoutWinner(byId.get(match.awaySource.matchId));
        if (winner !== match.awayId) {
          match.awayId = winner;
          changed = true;
        }
      }

      if (changed && (match.homeGoals !== null || match.awayGoals !== null)) {
        match.homeGoals = null;
        match.awayGoals = null;
        match.homePens = null;
        match.awayPens = null;
        resets += 1;
      }
    }
  }

  return { rounds: next, resets };
}

export function tournamentChampion(rounds: KnockoutRound[]): string | null {
  const final = rounds[rounds.length - 1];
  if (!final || final.matches.length === 0) return null;
  return knockoutWinner(final.matches[0]);
}

export function tournamentRunnerUp(rounds: KnockoutRound[]): string | null {
  const final = rounds[rounds.length - 1];
  if (!final || final.matches.length === 0) return null;
  return knockoutLoser(final.matches[0]);
}

/** Both beaten semi-finalists, used for the podium's third step. */
export function semiFinalLosers(rounds: KnockoutRound[]): string[] {
  const semi = rounds[rounds.length - 2];
  if (!semi) return [];
  return semi.matches.map((match) => knockoutLoser(match)).filter((id): id is string => Boolean(id));
}
