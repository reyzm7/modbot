"use client";

import { useState } from "react";
import { ListOrdered, Table2, TriangleAlert } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { PageIntro } from "@/components/layout/page-intro";
import { StepNav } from "@/components/layout/step-nav";
import { LeagueResults } from "@/components/tournament/league-results";
import { StandingsTable } from "@/components/tournament/standings-table";
import { Progress } from "@/components/ui/progress";
import { Tabs } from "@/components/ui/tabs";
import { useLeagueProgress, useTournament } from "@/hooks/use-tournament";

export default function LeaguePage() {
  const [tab, setTab] = useState("results");
  const progress = useLeagueProgress();
  const tournament = useTournament();
  const locked = Boolean(tournament?.qualifiedSnapshot);

  const remaining = progress.total - progress.played;

  return (
    <AppShell step="league">
      <PageIntro
        eyebrow="Étape 3 · Phase de ligue"
        title="Saisissez les résultats"
        description="Chaque score met le classement à jour immédiatement. Vous pouvez revenir corriger un résultat à tout moment."
        action={
          <Tabs
            value={tab}
            onValueChange={setTab}
            layoutId="league-tab"
            items={[
              { value: "results", label: "Résultats", icon: <Table2 className="size-4" /> },
              { value: "standings", label: "Classement", icon: <ListOrdered className="size-4" /> },
            ]}
          />
        }
      />

      <div className="mb-8">
        <div className="mb-2 flex items-baseline justify-between">
          <p className="eyebrow">Avancement</p>
          <p className="tabular text-xs text-muted-foreground">
            {progress.played} / {progress.total} matchs joués
          </p>
        </div>
        <Progress value={progress.percent} label="Matchs joués" />
      </div>

      {locked ? (
        <div className="glass mb-8 flex items-start gap-3 border-champagne/25 bg-champagne/[0.06] p-4">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-champagne" />
          <p className="text-sm leading-relaxed text-foreground/90">
            La phase finale est déjà tirée à partir de ce classement. Modifier un résultat change le
            tableau ci-dessous, mais plus la qualification. Pour la recalculer, retournez à
            l&apos;étape Qualification et relancez-la.
          </p>
        </div>
      ) : null}

      {tab === "results" ? <LeagueResults /> : <StandingsTable />}

      <StepNav
        backHref="/draw"
        nextHref="/qualification"
        nextDisabled={!progress.complete}
        hint={
          progress.complete
            ? "Tous les matchs sont joués."
            : `Encore ${remaining} match${remaining > 1 ? "s" : ""} à renseigner.`
        }
      />
    </AppShell>
  );
}
