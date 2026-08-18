"use client";

import { AppShell } from "@/components/layout/app-shell";
import { PageIntro } from "@/components/layout/page-intro";
import { DrawStage } from "@/components/tournament/draw-stage";

export default function DrawPage() {
  return (
    <AppShell step="draw">
      <PageIntro
        eyebrow="Étape 2 · Tirage au sort"
        title="Composez la phase de ligue"
        description="Les affiches se dévoilent une à une. Chaque équipe affronte des adversaires tous différents, une fois par journée."
      />
      <DrawStage />
    </AppShell>
  );
}
