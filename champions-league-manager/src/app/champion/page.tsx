"use client";

import { AppShell } from "@/components/layout/app-shell";
import { PageIntro } from "@/components/layout/page-intro";
import { StepNav } from "@/components/layout/step-nav";
import { ChampionStage } from "@/components/tournament/champion-stage";

export default function ChampionPage() {
  return (
    <AppShell step="champion">
      <PageIntro
        eyebrow="Étape 6 · Fin du tournoi"
        title="Le sacre"
        description="Tout le tournoi tient dans cette page : le champion, le podium et les chiffres marquants. Exportez-la en PDF depuis le menu."
      />
      <ChampionStage />
      <StepNav backHref="/knockout" hint="Tournoi terminé." />
    </AppShell>
  );
}
