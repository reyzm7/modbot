import { useTournamentStore } from "@/store/tournament-store";
import { computeStandings, isLeagueComplete, isPlayed } from "@/lib/standings";
import { knockoutWinner, tournamentChampion, tournamentRunnerUp } from "@/lib/knockout";
import { computeStats } from "@/lib/stats";

const store = useTournamentStore;
const get = () => {
  const t = store.getState().tournament;
  if (!t) throw new Error("no tournament");
  return t;
};

let failures = 0;
function check(label: string, condition: boolean, extra = "") {
  if (!condition) {
    failures += 1;
    console.log(`  FAIL  ${label} ${extra}`);
  } else {
    console.log(`  ok    ${label} ${extra}`);
  }
}

const CLUBS = [
  "Real Madrid","Manchester City","Bayern Munich","Paris Saint-Germain","Liverpool","Inter Milan",
  "Borussia Dortmund","RB Leipzig","Barcelone","Bayer Leverkusen","Atlético Madrid","Atalanta",
  "Juventus","Benfica","Arsenal","Club Bruges","Chelsea","AC Milan","Feyenoord","Sporting CP",
  "PSV Eindhoven","Séville","Naples","Porto","Ajax","Rangers","Celtic","Galatasaray",
  "Salzbourg","Shakhtar","Young Boys","Monaco","Marseille","Lille","Newcastle","Villarreal",
];

console.log("\n=== 1. Création + équipes ===");
store.getState().createTournament({ name: "Coupe des Clubs Champions", teamCount: 36 });
get().teams.forEach((team, index) => {
  store.getState().updateTeam(team.id, { name: CLUBS[index] });
});
check("36 équipes nommées", get().teams.every((t) => t.name.length > 0));
check("bracketSize = 16", get().bracketSize === 16, `(${get().bracketSize})`);

console.log("\n=== 2. Tirage ===");
const draw = store.getState().runDraw();
check("tirage valide", draw.ok, draw.issues.join(" | "));
const matches = get().league.matches;
check("144 affiches", matches.length === 144, `(${matches.length})`);

const seen = new Set<string>();
let duplicates = 0;
for (const m of matches) {
  const key = [m.homeId, m.awayId].sort().join("~");
  if (seen.has(key)) duplicates += 1;
  seen.add(key);
}
check("aucun adversaire en double", duplicates === 0, `(${duplicates})`);

const perDay = new Map<number, Set<string>>();
let dayClashes = 0;
for (const m of matches) {
  const set = perDay.get(m.matchday) ?? new Set<string>();
  if (set.has(m.homeId) || set.has(m.awayId)) dayClashes += 1;
  set.add(m.homeId);
  set.add(m.awayId);
  perDay.set(m.matchday, set);
}
check("une équipe joue 1 fois par journée", dayClashes === 0, `(${dayClashes})`);

const homeCount = new Map<string, number>();
for (const m of matches) homeCount.set(m.homeId, (homeCount.get(m.homeId) ?? 0) + 1);
const homeValues = [...homeCount.values()];
check("4 matchs à domicile pour tous", homeValues.every((v) => v === 4), `(min ${Math.min(...homeValues)}, max ${Math.max(...homeValues)})`);

store.getState().revealAll();
check("toutes les affiches révélées", get().league.revealed === 144);

console.log("\n=== 3. Scores de la phase de ligue ===");
let seed = 7;
const rnd = (max: number) => {
  seed = (seed * 1103515245 + 12345) % 2147483648;
  return Math.floor((seed / 2147483648) * max);
};
for (const m of get().league.matches) {
  store.getState().setLeagueScore(m.id, "home", rnd(5));
  store.getState().setLeagueScore(m.id, "away", rnd(4));
}
check("144 matchs joués", get().league.matches.filter(isPlayed).length === 144);
check("phase de ligue complète", isLeagueComplete(get().league.matches));

const standings = computeStandings(get().teams, get().league.matches);
check("36 lignes de classement", standings.length === 36);
check("rangs 1..36 continus", standings.every((row, i) => row.rank === i + 1));
let sortOk = true;
for (let i = 1; i < standings.length; i += 1) {
  const a = standings[i - 1];
  const b = standings[i];
  if (a.points < b.points) sortOk = false;
  else if (a.points === b.points && a.goalDiff < b.goalDiff) sortOk = false;
  else if (a.points === b.points && a.goalDiff === b.goalDiff && a.goalsFor < b.goalsFor) sortOk = false;
}
check("tri Points > Diff > BM respecté", sortOk);
check("chaque équipe a joué 8 matchs", standings.every((r) => r.played === 8));
const totalPoints = standings.reduce((s, r) => s + r.points, 0);
const draws = get().league.matches.filter((m) => m.homeGoals === m.awayGoals).length;
check("somme des points cohérente", totalPoints === 144 * 3 - draws, `(${totalPoints} vs ${144 * 3 - draws})`);

console.log("\n=== 4. Qualification ===");
const locked = store.getState().lockQualification();
check("qualification figée", locked === true);
check("snapshot de 36 équipes", (get().qualifiedSnapshot?.length ?? 0) === 36);
check("5 tours créés", get().knockout.length === 5, `(${get().knockout.map((r) => r.name).join(", ")})`);

console.log("\n=== 5. Phase finale ===");
const expectedTies = [8, 8, 4, 2, 1];
for (let index = 0; index < get().knockout.length; index += 1) {
  store.getState().drawKnockout(index);
  const round = get().knockout[index];
  check(`${round.name} : ${expectedTies[index]} confrontations`, round.matches.length === expectedTies[index], `(${round.matches.length})`);
  const filled = round.matches.every((m) => m.homeId && m.awayId);
  check(`${round.name} : toutes les places occupées`, filled);

  for (const m of round.matches) {
    const h = rnd(4);
    const a = rnd(4);
    store.getState().setKnockoutScore(m.id, "homeGoals", h);
    store.getState().setKnockoutScore(m.id, "awayGoals", a);
    if (h === a) {
      store.getState().setKnockoutScore(m.id, "homePens", 5);
      store.getState().setKnockoutScore(m.id, "awayPens", 4);
    }
  }
  const resolved = get().knockout[index].matches.every((m) => knockoutWinner(m) !== null);
  check(`${round.name} : tous départagés`, resolved);
}

const championId = tournamentChampion(get().knockout);
const runnerUpId = tournamentRunnerUp(get().knockout);
const nameOf = (id: string | null) => get().teams.find((t) => t.id === id)?.name ?? "—";
check("champion désigné", championId !== null, `→ ${nameOf(championId)}`);
check("finaliste désigné", runnerUpId !== null, `→ ${nameOf(runnerUpId)}`);
check("champion ≠ finaliste", championId !== runnerUpId);

console.log("\n=== 6. Propagation d'une correction ===");
const semi = get().knockout[3];
const tie = semi.matches[0];
const beforeWinner = knockoutWinner(tie);
const finalBefore = get().knockout[4].matches[0];

// Force the OTHER side through, whoever is currently winning: that is the only
// way the downstream tie genuinely changes participants.
const flipHome = beforeWinner === tie.awayId;
let resets = 0;
resets += store.getState().setKnockoutScore(tie.id, "homeGoals", flipHome ? 9 : 0);
resets += store.getState().setKnockoutScore(tie.id, "awayGoals", flipHome ? 0 : 9);

const afterWinner = knockoutWinner(get().knockout[3].matches[0]);
const finalAfter = get().knockout[4].matches[0];
check("vainqueur de demi-finale inversé", beforeWinner !== afterWinner, `(${nameOf(beforeWinner)} → ${nameOf(afterWinner)})`);
check("finale mise à jour en cascade", finalBefore.homeId !== finalAfter.homeId || finalBefore.awayId !== finalAfter.awayId);
check("score de la finale réinitialisé", finalAfter.homeGoals === null && finalAfter.awayGoals === null, `(resets=${resets})`);
check("plus de champion tant que la finale n'est pas rejouée", tournamentChampion(get().knockout) === null);

// A correction that does NOT change the winner must leave the bracket alone.
const quiet = store.getState().setKnockoutScore(tie.id, flipHome ? "homeGoals" : "awayGoals", 12);
check("correction sans changement de vainqueur : aucun reset", quiet === 0, `(resets=${quiet})`);

store.getState().setKnockoutScore(finalAfter.id, "homeGoals", 3);
store.getState().setKnockoutScore(finalAfter.id, "awayGoals", 1);
check("nouveau champion après re-saisie", tournamentChampion(get().knockout) !== null, `→ ${nameOf(tournamentChampion(get().knockout))}`);

console.log("\n=== 7. Statistiques ===");
const stats = computeStats(get());
check("total de matchs joués", stats.matchesPlayed === 144 + 23, `(${stats.matchesPlayed})`);
check("buts totaux > 0", stats.totalGoals > 0, `(${stats.totalGoals}, moy. ${stats.averageGoals.toFixed(2)})`);
check("plus large victoire trouvée", stats.biggestWin !== null, stats.biggestWin ? `(${stats.biggestWin.winnerGoals}-${stats.biggestWin.loserGoals}, ${stats.biggestWin.stage})` : "");
check("meilleure attaque", stats.bestAttack !== null, stats.bestAttack ? `${nameOf(stats.bestAttack.teamId)} (${stats.bestAttack.value})` : "");
check("meilleure défense", stats.bestDefense !== null, stats.bestDefense ? `${nameOf(stats.bestDefense.teamId)} (${stats.bestDefense.value})` : "");

console.log("\n=== 8. Exports ===");
const blobs: { name: string; size: number }[] = [];
(globalThis as any).URL.createObjectURL = () => "blob:mock";
(globalThis as any).URL.revokeObjectURL = () => undefined;
(globalThis as any).document = {
  createElement: () => ({ href: "", download: "", style: {}, click: () => undefined, remove: () => undefined, setAttribute: () => undefined }),
  body: { appendChild: () => undefined, removeChild: () => undefined },
};
const originalBlob = globalThis.Blob;
(globalThis as any).Blob = class extends originalBlob {
  constructor(parts: any[], options?: any) {
    super(parts, options);
    const size = parts.reduce((s: number, p: any) => s + (typeof p === "string" ? p.length : (p?.length ?? 0)), 0);
    blobs.push({ name: options?.type ?? "?", size });
  }
};

const { exportTournamentCsv, exportTournamentPdf } = await import("@/lib/export");
try {
  exportTournamentCsv(get());
  const csv = blobs.at(-1);
  check("CSV généré", (csv?.size ?? 0) > 2000, `(${csv?.size} octets, ${csv?.name})`);
} catch (error) {
  check("CSV généré", false, String(error));
}
try {
  exportTournamentPdf(get());
  check("PDF généré", true);
} catch (error) {
  check("PDF généré", false, String(error).slice(0, 120));
}

console.log("\n=== 9. Réinitialisation ===");
store.getState().clearLeagueScores();
check("scores effacés", get().league.matches.every((m) => m.homeGoals === null));
store.getState().resetTournament();
check("tournoi supprimé", store.getState().tournament === null);

console.log("\n=== 10. Balayage de toutes les tailles de tournoi ===");
for (let teamCount = 8; teamCount <= 36; teamCount += 2) {
  store.getState().resetTournament();
  store.getState().createTournament({ name: `Test ${teamCount}`, teamCount });
  get().teams.forEach((team, index) => {
    store.getState().updateTeam(team.id, { name: CLUBS[index] ?? `Club ${index + 1}` });
  });

  const result = store.getState().runDraw();
  if (!result.ok) {
    check(`${teamCount} équipes`, false, result.issues.join(" | "));
    continue;
  }
  store.getState().revealAll();

  for (const m of get().league.matches) {
    store.getState().setLeagueScore(m.id, "home", rnd(4));
    store.getState().setLeagueScore(m.id, "away", rnd(4));
  }
  if (!store.getState().lockQualification()) {
    check(`${teamCount} équipes`, false, "qualification refusée");
    continue;
  }

  for (let index = 0; index < get().knockout.length; index += 1) {
    store.getState().drawKnockout(index);
    for (const m of get().knockout[index].matches) {
      const h = rnd(4);
      const a = rnd(4);
      store.getState().setKnockoutScore(m.id, "homeGoals", h);
      store.getState().setKnockoutScore(m.id, "awayGoals", a);
      if (h === a) {
        store.getState().setKnockoutScore(m.id, "homePens", 5);
        store.getState().setKnockoutScore(m.id, "awayPens", 3);
      }
    }
  }

  const t = get();
  const champ = tournamentChampion(t.knockout);
  const emptySlot = t.knockout.some((r) => r.matches.some((m) => !m.homeId || !m.awayId));
  const stats = computeStats(t);
  const label = `${teamCount} équipes · ${t.matchesPerTeam} matchs · tableau à ${t.bracketSize}`;
  check(label, champ !== null && !emptySlot && stats.totalGoals > 0,
    `→ ${t.knockout.length} tours, champion ${nameOf(champ)}`);
}

console.log(failures === 0 ? "\n✅ TOUT PASSE\n" : `\n❌ ${failures} ÉCHEC(S)\n`);
process.exit(failures === 0 ? 0 : 1);
