"use client";

import { AppShell } from "@/components/layout/app-shell";
import { PageIntro } from "@/components/layout/page-intro";
import { StepNav } from "@/components/layout/step-nav";
import { KnockoutBoard } from "@/components/tournament/knockout-board";
import { useTournament } from "@/hooks/use-tournament";
import { tournamentChampion } from "@/lib/knockout";

export default function KnockoutPage() {
  const tournament = useTournament();
  const champion = tournament ? tournamentChampion(tournament.knockout) : null;

  return (
    <AppShell step="knockout">
      <PageIntro
        eyebrow="Étape 5 · Phase finale"
        title="Le tableau final"
        description="Tirez chaque tour, saisissez les scores et départagez aux tirs au but. Le vainqueur avance automatiquement ; corrigez un résultat et la suite du tableau se réécrit."
      />

      <KnockoutBoard />

      <StepNav
        backHref="/qualification"
        nextHref="/champion"
        nextLabel="Le sacre"
        nextDisabled={!champion}
        hint={champion ? "La finale est jouée." : "Déroulez le tableau jusqu'à la finale."}
      />
    </AppShell>
  );
}
