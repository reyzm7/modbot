import { jsPDF } from "jspdf";
import { autoTable } from "jspdf-autotable";

import { knockoutWinner, tournamentChampion } from "@/lib/knockout";
import { computeStandings, isPlayed, qualificationBand, BAND_SHORT } from "@/lib/standings";
import { computeStats, computeTeamAwards } from "@/lib/stats";
import type { Tournament } from "@/lib/types";
import { downloadBlob, formatSigned, slugify } from "@/lib/utils";

type AutoTableDoc = jsPDF & { lastAutoTable?: { finalY: number } };

const NAVY: [number, number, number] = [10, 17, 40];
const BLUE: [number, number, number] = [47, 107, 255];
const SLATE: [number, number, number] = [104, 116, 145];
const PAPER: [number, number, number] = [244, 247, 255];

function teamNameMap(tournament: Tournament): Map<string, string> {
  return new Map(tournament.teams.map((team) => [team.id, team.name]));
}

function scoreLabel(
  homeGoals: number | null,
  awayGoals: number | null,
  homePens?: number | null,
  awayPens?: number | null,
): string {
  if (homeGoals === null || awayGoals === null) return "— : —";
  const base = `${homeGoals} : ${awayGoals}`;
  if (homePens !== null && homePens !== undefined && awayPens !== null && awayPens !== undefined) {
    return `${base} (${homePens} : ${awayPens} t.a.b.)`;
  }
  return base;
}

/* -------------------------------------------------------------------------- */
/*                                    CSV                                     */
/* -------------------------------------------------------------------------- */

function csvCell(value: string | number): string {
  const text = String(value);
  return /[";\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function toCsv(rows: Array<Array<string | number>>): string {
  return rows.map((row) => row.map(csvCell).join(";")).join("\r\n");
}

export function exportTournamentCsv(tournament: Tournament): void {
  const names = teamNameMap(tournament);
  const standings = computeStandings(tournament.teams, tournament.league.matches);
  const rows: Array<Array<string | number>> = [];

  // En-tête : un CSV ne se met pas en forme, mais il peut être lisible.
  const champion = tournamentChampion(tournament.knockout);
  rows.push([tournament.name.toUpperCase()]);
  rows.push([
    `${tournament.teams.length} équipes`,
    `${tournament.matchesPerTeam} matchs par équipe`,
    `Format Ligue des Champions`,
  ]);
  rows.push([
    "Édité le",
    new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeStyle: "short" }).format(new Date()),
  ]);
  if (champion) rows.push(["Champion", names.get(champion) ?? ""]);
  rows.push([]);
  rows.push(["CLASSEMENT DE LA PHASE DE LIGUE"]);
  rows.push([
    "Position",
    "Club",
    "Chapeau",
    "Matchs",
    "Victoires",
    "Nuls",
    "Défaites",
    "Buts marqués",
    "Buts encaissés",
    "Différence",
    "Points",
    "Qualification",
  ]);

  const potOf = new Map(tournament.teams.map((team) => [team.id, team.pot]));
  for (const row of standings) {
    rows.push([
      row.rank,
      names.get(row.teamId) ?? "",
      potOf.get(row.teamId) ?? "",
      row.played,
      row.wins,
      row.draws,
      row.losses,
      row.goalsFor,
      row.goalsAgainst,
      formatSigned(row.goalDiff),
      row.points,
      BAND_SHORT[qualificationBand(row.rank, tournament.bracketSize)],
    ]);
  }

  rows.push([]);
  rows.push(["PHASE DE LIGUE — RÉSULTATS"]);
  rows.push(["Journée", "Domicile", "Score domicile", "Score extérieur", "Extérieur", "Statut"]);

  for (const match of [...tournament.league.matches].sort((a, b) => a.order - b.order)) {
    rows.push([
      match.matchday,
      names.get(match.homeId) ?? "",
      match.homeGoals ?? "",
      match.awayGoals ?? "",
      names.get(match.awayId) ?? "",
      isPlayed(match) ? "Joué" : "À jouer",
    ]);
  }

  if (tournament.knockout.some((round) => round.matches.length > 0)) {
    rows.push([]);
    rows.push(["PHASE FINALE"]);
    rows.push([
      "Tour",
      "Domicile",
      "Score domicile",
      "Score extérieur",
      "Extérieur",
      "T.a.b. domicile",
      "T.a.b. extérieur",
      "Qualifié",
    ]);

    for (const round of tournament.knockout) {
      for (const match of round.matches) {
        const winner = knockoutWinner(match);
        rows.push([
          round.name,
          names.get(match.homeId ?? "") ?? "À déterminer",
          match.homeGoals ?? "",
          match.awayGoals ?? "",
          names.get(match.awayId ?? "") ?? "À déterminer",
          match.homePens ?? "",
          match.awayPens ?? "",
          winner ? names.get(winner) ?? "" : "",
        ]);
      }
    }
  }

  const blob = new Blob([`\uFEFF${toCsv(rows)}`], { type: "text/csv;charset=utf-8;" });
  const teamPalmares = computeTeamAwards(tournament);
  if (teamPalmares.length > 0) {
    rows.push([]);
    rows.push(["PALMARÈS COLLECTIF"]);
    rows.push(["Distinction", "Club", "Performance"]);
    for (const award of teamPalmares) {
      rows.push([award.label, names.get(award.teamId) ?? "", award.value]);
    }
  }

  const individual: Array<[string, string]> = [
    ["MVP du tournoi", tournament.awards.mvp],
    ["Meilleur buteur", tournament.awards.topScorer],
    ["Meilleur passeur", tournament.awards.topAssister],
    ["Meilleur gardien", tournament.awards.topKeeper ?? ""],
  ].filter((entry): entry is [string, string] => Boolean(entry[1]?.trim()));

  if (individual.length > 0) {
    rows.push([]);
    rows.push(["DISTINCTIONS INDIVIDUELLES"]);
    for (const [label, name] of individual) rows.push([label, name]);
  }

  downloadBlob(blob, `${slugify(tournament.name)}.csv`);
}

/* -------------------------------------------------------------------------- */
/*                                    PDF                                     */
/* -------------------------------------------------------------------------- */

function sectionTitle(doc: jsPDF, title: string, y: number): number {
  doc.setFillColor(...BLUE);
  doc.rect(14, y - 4, 3, 6, "F");
  doc.setTextColor(...NAVY);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.text(title.toUpperCase(), 21, y);
  return y + 5;
}

function nextY(doc: AutoTableDoc, fallback: number): number {
  return (doc.lastAutoTable?.finalY ?? fallback) + 12;
}

export function exportTournamentPdf(tournament: Tournament): void {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" }) as AutoTableDoc;
  const pageWidth = doc.internal.pageSize.getWidth();
  const names = teamNameMap(tournament);
  const stats = computeStats(tournament);
  const standings = stats.standings;

  // Masthead. jsPDF ne connaît pas les dégradés : on empile de fines bandes
  // dont la couleur est interpolée, ce qui produit le même effet à l'impression.
  const HEAD_HEIGHT = 46;
  const STEPS = 60;
  for (let step = 0; step < STEPS; step += 1) {
    const ratio = step / (STEPS - 1);
    doc.setFillColor(
      Math.round(NAVY[0] + (BLUE[0] - NAVY[0]) * ratio * 0.55),
      Math.round(NAVY[1] + (BLUE[1] - NAVY[1]) * ratio * 0.55),
      Math.round(NAVY[2] + (BLUE[2] - NAVY[2]) * ratio * 0.55),
    );
    doc.rect((pageWidth / STEPS) * step, 0, pageWidth / STEPS + 0.6, HEAD_HEIGHT, "F");
  }

  doc.setFillColor(...BLUE);
  doc.rect(0, HEAD_HEIGHT, pageWidth, 1.4, "F");

  doc.setTextColor(...PAPER);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(24);
  doc.text(tournament.name, 14, 24, { maxWidth: pageWidth - 28 });

  doc.setFont("helvetica", "normal");
  doc.setFontSize(8.5);
  doc.setTextColor(168, 186, 232);
  doc.text(
    `${tournament.teams.length} équipes · ${tournament.matchesPerTeam} matchs par équipe · format Ligue des Champions`,
    14,
    33,
  );
  doc.text(
    `Édité le ${new Intl.DateTimeFormat("fr-FR", { dateStyle: "long" }).format(new Date())}`,
    14,
    38.5,
  );

  // Bandeau champion : la première chose que l'oeil doit trouver.
  let headerBottom = 60;
  const championId = tournamentChampion(tournament.knockout);
  if (championId) {
    doc.setFillColor(250, 244, 224);
    doc.roundedRect(14, 54, pageWidth - 28, 16, 2, 2, "F");
    doc.setFillColor(206, 168, 62);
    doc.rect(14, 54, 1.8, 16, "F");
    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.5);
    doc.setTextColor(150, 120, 40);
    doc.text("CHAMPION", 20, 60.5);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.setTextColor(92, 72, 18);
    doc.text(names.get(championId) ?? "", 20, 67, { maxWidth: pageWidth - 44 });
    headerBottom = 82;
  }

  let cursor = sectionTitle(doc, "Classement de la phase de ligue", headerBottom);

  autoTable(doc, {
    startY: cursor,
    head: [["#", "Club", "J", "G", "N", "P", "BM", "BE", "Diff", "Pts", "Qualification"]],
    body: standings.map((row) => [
      row.rank,
      names.get(row.teamId) ?? "",
      row.played,
      row.wins,
      row.draws,
      row.losses,
      row.goalsFor,
      row.goalsAgainst,
      formatSigned(row.goalDiff),
      row.points,
      BAND_SHORT[qualificationBand(row.rank, tournament.bracketSize)],
    ]),
    theme: "striped",
    styles: { fontSize: 8, cellPadding: 1.9, textColor: NAVY },
    headStyles: { fillColor: NAVY, textColor: PAPER, fontSize: 8 },
    alternateRowStyles: { fillColor: [246, 248, 253] },
    columnStyles: {
      0: { halign: "center", cellWidth: 9, fontStyle: "bold" },
      1: { cellWidth: 46 },
      9: { halign: "center", fontStyle: "bold" },
      10: { cellWidth: 26 },
    },
    didParseCell: (data) => {
      if (data.section !== "body" || data.column.index !== 0) return;
      const band = qualificationBand(Number(data.cell.raw), tournament.bracketSize);
      if (band === "direct") data.cell.styles.textColor = [22, 128, 90];
      if (band === "playoff") data.cell.styles.textColor = [47, 107, 255];
      if (band === "out") data.cell.styles.textColor = [190, 70, 90];
    },
  });

  cursor = sectionTitle(doc, "Phase de ligue — résultats", nextY(doc, cursor));

  const matchdays = [...new Set(tournament.league.matches.map((match) => match.matchday))].sort(
    (a, b) => a - b,
  );

  autoTable(doc, {
    startY: cursor,
    head: [["Journée", "Domicile", "Score", "Extérieur"]],
    body: matchdays.flatMap((day) =>
      tournament.league.matches
        .filter((match) => match.matchday === day)
        .sort((a, b) => a.order - b.order)
        .map((match) => [
          `J${day}`,
          names.get(match.homeId) ?? "",
          scoreLabel(match.homeGoals, match.awayGoals),
          names.get(match.awayId) ?? "",
        ]),
    ),
    theme: "striped",
    styles: { fontSize: 8, cellPadding: 2.2, textColor: NAVY, lineColor: [231, 236, 248], lineWidth: 0.1 },
    headStyles: { fillColor: NAVY, textColor: PAPER, fontSize: 7.5, cellPadding: 2.4 },
    alternateRowStyles: { fillColor: [247, 249, 254] },
    columnStyles: {
      0: { halign: "center", cellWidth: 18, textColor: SLATE },
      1: { halign: "right" },
      2: { halign: "center", cellWidth: 30, fontStyle: "bold" },
    },
  });

  const drawnRounds = tournament.knockout.filter((round) => round.matches.length > 0);
  if (drawnRounds.length > 0) {
    cursor = sectionTitle(doc, "Phase finale", nextY(doc, cursor));

    autoTable(doc, {
      startY: cursor,
      head: [["Tour", "Domicile", "Score", "Extérieur", "Qualifié"]],
      body: drawnRounds.flatMap((round) =>
        round.matches.map((match) => {
          const winner = knockoutWinner(match);
          return [
            round.name,
            names.get(match.homeId ?? "") ?? "À déterminer",
            scoreLabel(match.homeGoals, match.awayGoals, match.homePens, match.awayPens),
            names.get(match.awayId ?? "") ?? "À déterminer",
            winner ? names.get(winner) ?? "" : "—",
          ];
        }),
      ),
      theme: "grid",
      styles: { fontSize: 8, cellPadding: 1.6, textColor: NAVY, lineColor: [225, 231, 245] },
      headStyles: { fillColor: NAVY, textColor: PAPER, fontSize: 8 },
      columnStyles: {
        0: { cellWidth: 32, textColor: SLATE },
        1: { halign: "right" },
        2: { halign: "center", cellWidth: 34, fontStyle: "bold" },
        4: { fontStyle: "bold" },
      },
    });
  }

  cursor = sectionTitle(doc, "Statistiques", nextY(doc, cursor));

  const statRows: string[][] = [
    ["Matchs joués", `${stats.matchesPlayed} / ${stats.matchesTotal}`],
    ["Buts inscrits", String(stats.totalGoals)],
    ["Moyenne par match", stats.averageGoals.toFixed(2)],
  ];

  if (stats.biggestWin) {
    statRows.push([
      "Plus large victoire",
      `${names.get(stats.biggestWin.winnerId) ?? ""} ${stats.biggestWin.winnerGoals} - ${
        stats.biggestWin.loserGoals
      } ${names.get(stats.biggestWin.loserId) ?? ""} (${stats.biggestWin.stage})`,
    ]);
  }
  if (stats.bestAttack) {
    statRows.push([
      "Meilleure attaque (ligue)",
      `${names.get(stats.bestAttack.teamId) ?? ""} — ${stats.bestAttack.value} buts`,
    ]);
  }
  if (stats.bestDefense) {
    statRows.push([
      "Meilleure défense (ligue)",
      `${names.get(stats.bestDefense.teamId) ?? ""} — ${stats.bestDefense.value} buts encaissés`,
    ]);
  }
  if (tournament.awards.mvp) statRows.push(["MVP du tournoi", tournament.awards.mvp]);
  if (tournament.awards.topScorer) statRows.push(["Meilleur buteur", tournament.awards.topScorer]);
  if (tournament.awards.topKeeper) {
    statRows.push(["Meilleur gardien", tournament.awards.topKeeper]);
  }
  if (tournament.awards.topAssister) {
    statRows.push(["Meilleur passeur", tournament.awards.topAssister]);
  }

  autoTable(doc, {
    startY: cursor,
    body: statRows,
    theme: "plain",
    styles: { fontSize: 9.5, cellPadding: 2.6, textColor: NAVY },
    columnStyles: {
      0: { cellWidth: 55, textColor: SLATE },
      1: { fontStyle: "bold" },
    },
  });

  const pageCount = doc.getNumberOfPages();
  for (let page = 1; page <= pageCount; page += 1) {
    doc.setPage(page);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.5);
    doc.setTextColor(...SLATE);
    const footY = doc.internal.pageSize.getHeight() - 8;
    doc.setDrawColor(226, 232, 246);
    doc.setLineWidth(0.3);
    doc.line(14, footY - 4, pageWidth - 14, footY - 4);
    doc.text(tournament.name, 14, footY);
    doc.text(`${page} / ${pageCount}`, pageWidth - 14, footY, { align: "right" });
  }

  doc.save(`${slugify(tournament.name)}.pdf`);
}
