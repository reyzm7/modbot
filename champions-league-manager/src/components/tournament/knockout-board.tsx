"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Crown, Lock, Shuffle, Trophy } from "lucide-react";
import { toast } from "sonner";

import { MatchPoster } from "@/components/tournament/match-poster";
import { ScoreInput } from "@/components/tournament/score-input";
import { SoccerBall } from "@/components/tournament/soccer-ball";
import { TeamCrest } from "@/components/tournament/team-crest";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useTeamMap, useTournament } from "@/hooks/use-tournament";
import { canDrawRound, isRoundComplete, knockoutWinner, needsShootout } from "@/lib/knockout";
import type { KnockoutMatch, KnockoutRound } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useTournamentStore } from "@/store/tournament-store";

function KnockoutTie({ match, isFinal }: { match: KnockoutMatch; isFinal: boolean }) {
  const teams = useTeamMap();
  const setKnockoutScore = useTournamentStore((state) => state.setKnockoutScore);

  const home = match.homeId ? teams.get(match.homeId) : null;
  const away = match.awayId ? teams.get(match.awayId) : null;
  const winner = knockoutWinner(match);
  const level = needsShootout(match);
  const ready = Boolean(match.homeId && match.awayId);

  function update(
    field: "homeGoals" | "awayGoals" | "homePens" | "awayPens",
    value: number | null,
  ) {
    const resets = setKnockoutScore(match.id, field, value);
    if (resets > 0) {
      toast.info("Suite du tableau réinitialisée", {
        description: `${resets} match${resets > 1 ? "s" : ""} en aval attend${resets > 1 ? "ent" : ""} un nouveau score.`,
      });
    }
  }

  return (
    <div
      className={cn(
        "glass p-3",
        isFinal && winner && "border-champagne/35 bg-champagne/[0.05]",
      )}
    >
      <div className="flex items-center gap-2 sm:gap-3">
        <div
          className={cn(
            "flex min-w-0 flex-1 items-center justify-end gap-2 text-right",
            winner === match.homeId ? "text-foreground" : "text-foreground/70",
          )}
        >
          <span className="min-w-0 truncate text-sm font-medium">
            {home?.name ?? "À déterminer"}
          </span>
          <TeamCrest team={home} size="sm" />
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          <ScoreInput
            value={match.homeGoals}
            onChange={(value) => update("homeGoals", value)}
            label={`Buts de ${home?.name ?? "l'équipe à domicile"}`}
            className={cn(
              !ready && "opacity-40",
              winner === match.homeId && "border-mint/45 text-mint",
            )}
          />
          <span aria-hidden className="text-xs text-muted-foreground">
            :
          </span>
          <ScoreInput
            value={match.awayGoals}
            onChange={(value) => update("awayGoals", value)}
            label={`Buts de ${away?.name ?? "l'équipe à l'extérieur"}`}
            className={cn(
              !ready && "opacity-40",
              winner === match.awayId && "border-mint/45 text-mint",
            )}
          />
        </div>

        <div
          className={cn(
            "flex min-w-0 flex-1 items-center gap-2",
            winner === match.awayId ? "text-foreground" : "text-foreground/70",
          )}
        >
          <TeamCrest team={away} size="sm" />
          <span className="min-w-0 truncate text-sm font-medium">
            {away?.name ?? "À déterminer"}
          </span>
        </div>
      </div>

      <AnimatePresence>
        {level ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-2.5 flex items-center justify-center gap-2 border-t border-white/10 pt-2.5">
              <span className="eyebrow">Tirs au but</span>
              <ScoreInput
                tone="pens"
                value={match.homePens}
                onChange={(value) => update("homePens", value)}
                label={`Tirs au but de ${home?.name ?? "l'équipe à domicile"}`}
              />
              <span aria-hidden className="text-xs text-muted-foreground">
                :
              </span>
              <ScoreInput
                tone="pens"
                value={match.awayPens}
                onChange={(value) => update("awayPens", value)}
                label={`Tirs au but de ${away?.name ?? "l'équipe à l'extérieur"}`}
              />
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {winner ? (
        <p className="mt-2.5 flex items-center justify-center gap-1.5 text-xs text-mint">
          {isFinal ? <Trophy className="size-3" /> : <Crown className="size-3" />}
          {isFinal ? "Champion" : "Qualifié"} : {teams.get(winner)?.name}
        </p>
      ) : null}
    </div>
  );
}

function RoundSection({
  round,
  index,
  total,
}: {
  round: KnockoutRound;
  index: number;
  total: number;
}) {
  const tournament = useTournament();
  const drawKnockout = useTournamentStore((state) => state.drawKnockout);
  const teams = useTeamMap();
  const [drawing, setDrawing] = useState(false);
  const [revealIndex, setRevealIndex] = useState<number | null>(null);
  const [showAway, setShowAway] = useState(false);

  const tieCount = round.matches.length;

  useEffect(() => {
    if (revealIndex === null) return;
    if (revealIndex >= tieCount) {
      setRevealIndex(null);
      return;
    }
    // Le qualifié apparaît, puis son adversaire trois quarts de seconde plus tard.
    const opponent = setTimeout(() => setShowAway(true), 2000);
    const nextTie = setTimeout(() => {
      setShowAway(false);
      setRevealIndex((index) => (index ?? 0) + 1);
    }, 4600);
    return () => {
      clearTimeout(opponent);
      clearTimeout(nextTie);
    };
  }, [revealIndex, tieCount]);

  if (!tournament) return null;

  const drawable = canDrawRound(tournament.knockout, index);
  const complete = isRoundComplete(round);
  const isFinal = index === total - 1;

  function handleDraw() {
    setDrawing(true);
    window.setTimeout(() => {
      drawKnockout(index);
      setDrawing(false);
      setShowAway(false);
      setRevealIndex(0);
    }, 2600);
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.06, 0.3), duration: 0.4 }}
      aria-labelledby={`round-${round.id}`}
    >
      <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <h2
            id={`round-${round.id}`}
            className={cn(
              "font-display text-base font-bold tracking-tight",
              isFinal && "text-champagne",
            )}
          >
            {round.name}
          </h2>
          {round.drawn ? (
            complete ? (
              <Badge variant="success">Terminé</Badge>
            ) : (
              <Badge>En cours</Badge>
            )
          ) : (
            <Badge variant="neutral">{drawable ? "À tirer" : "Verrouillé"}</Badge>
          )}
        </div>

        {!round.drawn ? (
          <Button size="sm" onClick={handleDraw} disabled={!drawable || drawing}>
            <Shuffle />
            {drawing ? "Tirage…" : "Tirer"}
          </Button>
        ) : null}
      </header>

      {drawing ? (
        <div className="glass grid h-40 place-items-center">
          <div className="text-center">
            <SoccerBall rolling className="mx-auto size-14" />
            <p className="eyebrow mt-4">Tirage de {round.name.toLowerCase()}</p>
          </div>
        </div>
      ) : revealIndex !== null && round.matches[revealIndex] ? (
        <div>
          <MatchPoster
            key={round.matches[revealIndex].id}
            home={
              round.matches[revealIndex].homeId
                ? teams.get(round.matches[revealIndex].homeId as string)
                : null
            }
            away={
              round.matches[revealIndex].awayId
                ? teams.get(round.matches[revealIndex].awayId as string)
                : null
            }
            showAway={showAway}
            label={`${round.name} · affiche ${revealIndex + 1} / ${tieCount}`}
          />
          <div className="mt-3 flex justify-center">
            <Button variant="ghost" size="sm" onClick={() => setRevealIndex(null)}>
              Passer le tirage
            </Button>
          </div>
        </div>
      ) : round.drawn ? (
        <div className="relative pl-5">
          {/* Colonne du tableau : elle se trace de haut en bas au moment du tirage. */}
          <motion.span
            aria-hidden
            initial={{ scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ duration: 0.75, ease: "easeOut" }}
            className="absolute bottom-5 left-1 top-5 w-px origin-top bg-gradient-to-b from-primary/70 via-primary/40 to-primary/5"
          />

          <ul className="grid gap-2">
            {round.matches.map((match, position) => {
              const beat = 0.28 + Math.min(position * 0.08, 0.6);
              return (
                <motion.li
                  key={match.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(position * 0.06, 0.5), duration: 0.35 }}
                  className="relative"
                >
                  <motion.span
                    aria-hidden
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ delay: beat, duration: 0.28, ease: "easeOut" }}
                    className="absolute -left-[11px] top-[27px] h-px w-3 origin-left bg-primary/45"
                  />
                  <motion.span
                    aria-hidden
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: beat + 0.1, type: "spring", stiffness: 340, damping: 20 }}
                    className={cn(
                      "absolute -left-[19px] top-6 size-2 rounded-full border bg-background",
                      isFinal ? "border-champagne/70" : "border-primary/70",
                    )}
                  />
                  <KnockoutTie match={match} isFinal={isFinal} />
                </motion.li>
              );
            })}
          </ul>
        </div>
      ) : (
        <div className="glass flex items-center gap-3 p-5 text-sm text-muted-foreground">
          <Lock className="size-4 shrink-0" />
          {drawable
            ? "Lancez le tirage de ce tour."
            : index === 0
              ? "La qualification doit d'abord être validée."
              : `Terminez ${tournament.knockout[index - 1]?.name.toLowerCase()} pour débloquer ce tour.`}
        </div>
      )}
    </motion.section>
  );
}

export function KnockoutBoard() {
  const tournament = useTournament();
  if (!tournament) return null;

  return (
    <div className="space-y-10">
      {tournament.knockout.map((round, index) => (
        <RoundSection
          key={round.id}
          round={round}
          index={index}
          total={tournament.knockout.length}
        />
      ))}
    </div>
  );
}
