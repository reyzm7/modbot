"use client";

import { useEffect, useMemo } from "react";
import { AlertTriangle, Minus, Plus } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import { PageIntro } from "@/components/layout/page-intro";
import { StepNav } from "@/components/layout/step-nav";
import { LogoPicker } from "@/components/tournament/logo-picker";
import { TeamEditor } from "@/components/tournament/team-editor";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useHydrated, useTournament } from "@/hooks/use-tournament";
import { allowedMatchCounts, MAX_TEAMS, MIN_TEAMS } from "@/lib/draw";
import { cn } from "@/lib/utils";
import { useTournamentStore } from "@/store/tournament-store";

const TEAM_PRESETS = [8, 16, 24, 32, 36];

export default function SetupPage() {
  const hydrated = useHydrated();
  const tournament = useTournament();
  const createTournament = useTournamentStore((state) => state.createTournament);

  useEffect(() => {
    if (hydrated && !tournament) {
      createTournament({ name: "", teamCount: 16 });
    }
  }, [hydrated, tournament, createTournament]);

  if (!hydrated || !tournament) {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-4 px-4 py-10 sm:px-6">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <AppShell step="setup">
      <SetupContent />
    </AppShell>
  );
}

function SetupContent() {
  const tournament = useTournament();
  const updateIdentity = useTournamentStore((state) => state.updateIdentity);
  const setTeamCount = useTournamentStore((state) => state.setTeamCount);
  const setMatchesPerTeam = useTournamentStore((state) => state.setMatchesPerTeam);
  const resetDraw = useTournamentStore((state) => state.resetDraw);

  const summary = useMemo(() => {
    if (!tournament) return null;
    const { teams, matchesPerTeam, bracketSize } = tournament;
    return {
      totalMatches: (teams.length * matchesPerTeam) / 2,
      matchesPerDay: teams.length / 2,
      direct: bracketSize / 2,
      playoff: bracketSize,
      eliminated: teams.length - bracketSize / 2 - bracketSize,
    };
  }, [tournament]);

  if (!tournament || !summary) return null;

  const locked = tournament.league.drawn;
  const nameValid = tournament.name.trim().length >= 2;
  const missing = tournament.teams.filter((team) => team.name.trim().length === 0).length;
  const ready = nameValid && missing === 0;

  const hint = !nameValid
    ? "Donnez un nom à votre tournoi pour continuer."
    : missing > 0
      ? `Encore ${missing} équipe${missing > 1 ? "s" : ""} à nommer.`
      : undefined;

  function changeTeamCount(next: number) {
    if (locked) return;
    setTeamCount(next);
  }

  function handleResetDraw() {
    resetDraw();
    toast.success("Tirage annulé", { description: "Vous pouvez de nouveau modifier le plateau." });
  }

  return (
    <>
      <PageIntro
        eyebrow="Étape 1 · Configuration"
        title="Créez votre tournoi"
        description="Nommez la compétition, choisissez la taille du plateau, puis renseignez chaque équipe. Tout est enregistré au fil de la saisie."
      />

      {locked ? (
        <div className="glass mb-6 flex flex-wrap items-center gap-3 border-champagne/25 bg-champagne/[0.06] p-4">
          <AlertTriangle className="size-4 shrink-0 text-champagne" />
          <p className="min-w-0 flex-1 text-sm text-foreground/90">
            Le tirage est déjà effectué : la taille du plateau est verrouillée. Vous pouvez encore
            renommer les équipes et ajouter des logos.
          </p>
          <Button variant="secondary" size="sm" onClick={handleResetDraw}>
            Annuler le tirage
          </Button>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Identité</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="tournament-name">Nom du tournoi</Label>
              <Input
                id="tournament-name"
                value={tournament.name}
                maxLength={60}
                placeholder="Coupe des étoiles 2026"
                onChange={(event) => updateIdentity({ name: event.target.value })}
                className="mt-1.5"
                aria-describedby="tournament-name-hint"
              />
              <p id="tournament-name-hint" className="mt-1.5 text-xs text-muted-foreground">
                Il apparaît en tête de tous les exports.
              </p>
            </div>

            <div>
              <Label htmlFor="tournament-logo">Logo du tournoi</Label>
              <div className="mt-1.5 flex items-center gap-3">
                <LogoPicker
                  label="Logo du tournoi"
                  size="lg"
                  value={tournament.logo}
                  onChange={(logo) => updateIdentity({ logo })}
                  onClear={() => updateIdentity({ logo: null })}
                />
                <p className="text-xs text-muted-foreground">
                  Facultatif. L&apos;image est réduite avant d&apos;être enregistrée.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Format</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <Label htmlFor="team-count">Nombre d&apos;équipes</Label>
              <div className="mt-1.5 flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="icon"
                  aria-label="Retirer deux équipes"
                  disabled={locked || tournament.teams.length <= MIN_TEAMS}
                  onClick={() => changeTeamCount(tournament.teams.length - 2)}
                >
                  <Minus />
                </Button>
                <Input
                  id="team-count"
                  type="number"
                  inputMode="numeric"
                  min={MIN_TEAMS}
                  max={MAX_TEAMS}
                  step={2}
                  disabled={locked}
                  value={tournament.teams.length}
                  onChange={(event) => changeTeamCount(Number(event.target.value))}
                  className="w-20 text-center font-display font-bold"
                />
                <Button
                  variant="secondary"
                  size="icon"
                  aria-label="Ajouter deux équipes"
                  disabled={locked || tournament.teams.length >= MAX_TEAMS}
                  onClick={() => changeTeamCount(tournament.teams.length + 2)}
                >
                  <Plus />
                </Button>

                <div className="ml-1 flex flex-wrap gap-1.5">
                  {TEAM_PRESETS.map((preset) => (
                    <Button
                      key={preset}
                      variant={tournament.teams.length === preset ? "default" : "outline"}
                      size="sm"
                      disabled={locked}
                      onClick={() => changeTeamCount(preset)}
                    >
                      {preset}
                    </Button>
                  ))}
                </div>
              </div>
              <p className="mt-1.5 text-xs text-muted-foreground">
                Nombre pair, de {MIN_TEAMS} à {MAX_TEAMS}. Réparti en {tournament.potCount} chapeaux.
              </p>
            </div>

            <div>
              <Label id="matches-label">Matchs par équipe</Label>
              <div
                role="group"
                aria-labelledby="matches-label"
                className="mt-1.5 flex flex-wrap gap-1.5"
              >
                {allowedMatchCounts(tournament.teams.length).map((count) => (
                  <Button
                    key={count}
                    variant={tournament.matchesPerTeam === count ? "default" : "outline"}
                    size="sm"
                    disabled={locked}
                    aria-pressed={tournament.matchesPerTeam === count}
                    onClick={() => setMatchesPerTeam(count)}
                  >
                    {count}
                  </Button>
                ))}
              </div>
              <p className="mt-1.5 text-xs text-muted-foreground">
                Autant de journées que de matchs par équipe.
              </p>
            </div>

            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-white/10 pt-4 text-sm sm:grid-cols-4">
              {[
                { label: "Matchs", value: summary.totalMatches },
                { label: "Journées", value: tournament.matchesPerTeam },
                { label: "Qualifiés", value: summary.direct },
                { label: "Barrages", value: summary.playoff },
              ].map((item) => (
                <div key={item.label}>
                  <dt className="eyebrow">{item.label}</dt>
                  <dd className="tabular mt-0.5 font-display text-lg font-bold">{item.value}</dd>
                </div>
              ))}
            </dl>

            <p className={cn("text-xs", summary.eliminated > 0 ? "text-muted-foreground" : "text-mint")}>
              {summary.eliminated > 0
                ? `${summary.eliminated} équipe${summary.eliminated > 1 ? "s" : ""} sortiront après la phase de ligue.`
                : "Toutes les équipes accèdent à la phase finale."}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="mt-10">
        <TeamEditor />
      </div>

      <StepNav backHref="/" backLabel="Accueil" nextHref="/draw" nextDisabled={!ready} hint={hint} />
    </>
  );
}
