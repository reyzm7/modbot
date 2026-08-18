"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FastForward, Shuffle, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { StepNav } from "@/components/layout/step-nav";
import { MatchPoster } from "@/components/tournament/match-poster";
import { SoccerBall } from "@/components/tournament/soccer-ball";
import { TeamCrest } from "@/components/tournament/team-crest";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useTeamMap, useTournament } from "@/hooks/use-tournament";
import type { Tournament } from "@/lib/types";
import { useTournamentStore } from "@/store/tournament-store";

type Phase = "idle" | "shuffling" | "revealing" | "done";

/** Deux noms qui défilent vite : on croit voir la machine hésiter. */
function NameScramble({ teams }: { teams: Tournament["teams"] }) {
  const [pair, setPair] = useState<[string, string]>(["", ""]);

  useEffect(() => {
    if (teams.length < 2) return;
    const pick = () => teams[Math.floor(Math.random() * teams.length)]?.name ?? "";

    let delay = 55;
    let timer = 0;
    const tick = () => {
      setPair([pick(), pick()]);
      delay = Math.min(delay * 1.16, 280);
      timer = window.setTimeout(tick, delay);
    };
    timer = window.setTimeout(tick, delay);
    return () => clearTimeout(timer);
  }, [teams]);

  return (
    <p className="mt-8 flex items-center justify-center gap-3 font-display text-base font-bold tracking-tight sm:text-xl">
      <span className="w-[38vw] max-w-[190px] truncate text-right text-foreground/80 blur-[0.4px]">
        {pair[0]}
      </span>
      <span className="shrink-0 text-xs text-primary">VS</span>
      <span className="w-[38vw] max-w-[190px] truncate text-left text-foreground/80 blur-[0.4px]">
        {pair[1]}
      </span>
    </p>
  );
}

export function DrawStage() {
  const tournament = useTournament();
  const teams = useTeamMap();
  const runDraw = useTournamentStore((state) => state.runDraw);
  const revealNext = useTournamentStore((state) => state.revealNext);
  const revealAll = useTournamentStore((state) => state.revealAll);
  const [shuffling, setShuffling] = useState(false);
  const [awayVisible, setAwayVisible] = useState(false);

  const matches = useMemo(
    () => [...(tournament?.league.matches ?? [])].sort((a, b) => a.order - b.order),
    [tournament],
  );

  const revealed = tournament?.league.revealed ?? 0;
  const total = matches.length;
  const drawn = Boolean(tournament?.league.drawn);

  const phase: Phase = shuffling
    ? "shuffling"
    : !drawn
      ? "idle"
      : revealed >= total
        ? "done"
        : "revealing";

  const current = revealed > 0 ? matches[revealed - 1] : null;
  const upcoming = revealed < total ? matches[revealed] : null;

  const currentId = current?.id;
  useEffect(() => {
    if (!currentId) return;
    // L'adversaire se dévoile après coup : c'est là que se joue le suspense.
    setAwayVisible(false);
    const timer = setTimeout(() => setAwayVisible(true), 2000);
    return () => clearTimeout(timer);
  }, [currentId]);

  useEffect(() => {
    if (!shuffling) return;
    const timer = setTimeout(() => {
      setShuffling(false);
      revealNext();
    }, 2900);
    return () => clearTimeout(timer);
  }, [shuffling, revealNext]);

  if (!tournament) return null;

  const grouped = [...new Map<number, typeof tournament.teams>(
    tournament.teams.reduce((map, team) => {
      map.set(team.pot, [...(map.get(team.pot) ?? []), team]);
      return map;
    }, new Map<number, typeof tournament.teams>()),
  ).entries()].sort((a, b) => a[0] - b[0]);

  function handleDraw() {
    const result = runDraw();
    if (!result.ok) {
      toast.error("Tirage impossible", { description: result.issues[0] });
      return;
    }
    setShuffling(true);
  }

  function handleRevealAll() {
    revealAll();
    toast.success("Tirage complet", { description: `${total} affiches dévoilées.` });
  }

  function handleNext() {
    revealNext();
  }

  /* ----------------------------- Before the draw ---------------------------- */
  if (phase === "idle") {
    return (
      <>
        <div className="space-y-6">
          {grouped.map(([pot, potTeams]) => (
            <section key={pot}>
              <p className="eyebrow mb-2.5">Chapeau {pot}</p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
                {potTeams.map((team) => (
                  <motion.div
                    key={team.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className="glass flex items-center gap-2.5 p-2.5"
                  >
                    <TeamCrest team={team} size="sm" />
                    <span className="min-w-0 truncate text-sm font-medium">{team.name}</span>
                  </motion.div>
                ))}
              </div>
            </section>
          ))}
        </div>

        <div className="glass surface-sheen mt-8 flex flex-col items-center gap-4 p-8 text-center">
          <Sparkles className="size-6 text-primary" />
          <div>
            <h2 className="font-display text-lg font-bold tracking-tight">
              Prêt pour le tirage au sort
            </h2>
            <p className="mx-auto mt-1.5 max-w-md text-sm text-muted-foreground">
              {(tournament.teams.length * tournament.matchesPerTeam) / 2} affiches réparties sur{" "}
              {tournament.matchesPerTeam} journées. Aucune équipe ne croisera deux fois le même
              adversaire.
            </p>
          </div>
          <Button size="lg" onClick={handleDraw}>
            <Shuffle />
            Tirer les matchs
          </Button>
        </div>

        <StepNav
          backHref="/setup"
          hint="Lancez le tirage pour continuer."
          nextDisabled
          nextLabel="Suivant"
          onNext={() => undefined}
        />
      </>
    );
  }

  /* ------------------------------ Drawing balls ----------------------------- */
  if (phase === "shuffling") {
    return (
      <div className="grid min-h-[46vh] place-items-center">
        <div className="text-center">
          <div className="relative mx-auto size-24">
            <span className="absolute inset-0 animate-pulse-ring rounded-full border border-primary/50" />
            <SoccerBall rolling className="absolute inset-3" />
          </div>
          <p className="eyebrow mt-6">Tirage en cours</p>
          <p className="mt-2 font-display text-lg font-semibold tracking-tight">
            Composition de la phase de ligue…
          </p>
          <NameScramble teams={tournament.teams} />
        </div>
      </div>
    );
  }

  /* --------------------------- Reveal, one by one --------------------------- */
  const percent = total ? (revealed / total) * 100 : 0;

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Badge variant="neutral">
            Affiche {Math.min(revealed, total)} / {total}
          </Badge>
          {current ? <Badge>Journée {current.matchday}</Badge> : null}
        </div>

        {phase === "revealing" ? (
          <Button variant="ghost" size="sm" onClick={handleRevealAll}>
            <FastForward />
            Tout révéler
          </Button>
        ) : null}
      </div>

      <Progress value={percent} label="Affiches dévoilées" className="mb-6" />

      <div className="min-h-[220px]">
        <AnimatePresence mode="wait">
          {current ? (
            <motion.div
              key={current.id}
              initial={{ opacity: 0, scale: 0.94, y: 14 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.97, y: -10 }}
              transition={{ type: "spring", stiffness: 240, damping: 24 }}
              className="relative overflow-hidden rounded-xl"
            >
              <MatchPoster
                home={teams.get(current.homeId)}
                away={teams.get(current.awayId)}
                label={`Journée ${current.matchday}`}
                showAway={awayVisible}
                footnote={
                  upcoming
                    ? "Appuyez sur Suivant pour dévoiler l'affiche suivante."
                    : "Toutes les affiches sont dévoilées."
                }
              />

              {/* Éclair d'apparition, puis balayage de projecteur sur l'affiche. */}
              <motion.span
                aria-hidden
                initial={{ opacity: 0.55 }}
                animate={{ opacity: 0 }}
                transition={{ duration: 0.45, ease: "easeOut" }}
                className="pointer-events-none absolute inset-0 bg-white"
              />
              <motion.span
                aria-hidden
                initial={{ x: "-130%" }}
                animate={{ x: "130%" }}
                transition={{ duration: 0.85, ease: [0.22, 1, 0.36, 1], delay: 0.1 }}
                className="pointer-events-none absolute inset-y-0 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-white/18 to-transparent"
              />
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      {revealed > 1 ? (
        <section className="mt-8" aria-label="Affiches déjà dévoilées">
          <p className="eyebrow mb-3">Déjà tirées</p>
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {matches
              .slice(0, Math.max(0, revealed - 1))
              .reverse()
              .slice(0, 12)
              .map((match) => (
                <motion.li
                  key={match.id}
                  layout
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="glass flex items-center gap-2 px-3 py-2 text-sm"
                >
                  <span className="tabular w-8 shrink-0 text-xs text-muted-foreground">
                    J{match.matchday}
                  </span>
                  <TeamCrest team={teams.get(match.homeId)} size="xs" />
                  <span className="min-w-0 flex-1 truncate text-right">
                    {teams.get(match.homeId)?.name}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">—</span>
                  <span className="min-w-0 flex-1 truncate">{teams.get(match.awayId)?.name}</span>
                  <TeamCrest team={teams.get(match.awayId)} size="xs" />
                </motion.li>
              ))}
          </ul>
          {revealed - 1 > 12 ? (
            <p className="mt-3 text-xs text-muted-foreground">
              + {revealed - 1 - 12} autres affiches déjà tirées.
            </p>
          ) : null}
        </section>
      ) : null}

      {phase === "done" ? (
        <StepNav
          backHref="/setup"
          nextHref="/league"
          nextLabel="Résultats"
          hint="Le tirage est terminé."
        />
      ) : (
        <StepNav
          backHref="/setup"
          nextLabel="Suivant"
          onNext={handleNext}
          hint={`Encore ${total - revealed} affiche${total - revealed > 1 ? "s" : ""} à dévoiler.`}
        />
      )}
    </>
  );
}
