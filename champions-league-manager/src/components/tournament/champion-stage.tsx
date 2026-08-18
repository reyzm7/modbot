"use client";

import { useEffect, useMemo, useRef } from "react";
import { motion } from "framer-motion";
import {
  Award,
  Flame,
  Goal,
  Hand,
  Handshake,
  Medal,
  Shield,
  Sparkles,
  Star,
  TrendingDown,
  Trophy,
  Users,
} from "lucide-react";

import { TeamCrest } from "@/components/tournament/team-crest";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useTeamMap, useTournament } from "@/hooks/use-tournament";
import { semiFinalLosers, tournamentChampion, tournamentRunnerUp } from "@/lib/knockout";
import { computeStats, computeTeamAwards } from "@/lib/stats";
import type { Awards } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useTournamentStore } from "@/store/tournament-store";

const AWARD_FIELDS: Array<{
  key: keyof Awards;
  label: string;
  caption: string;
  placeholder: string;
  icon: typeof Star;
}> = [
  {
    key: "mvp",
    label: "MVP du tournoi",
    caption: "Le joueur de la compétition",
    placeholder: "Nom du joueur",
    icon: Star,
  },
  {
    key: "topScorer",
    label: "Meilleur buteur",
    caption: "Le plus décisif devant",
    placeholder: "Nom du joueur",
    icon: Goal,
  },
  {
    key: "topAssister",
    label: "Meilleur passeur",
    caption: "Le meilleur dernier geste",
    placeholder: "Nom du joueur",
    icon: Handshake,
  },
  {
    key: "topKeeper",
    label: "Meilleur gardien",
    caption: "Le mur du tournoi",
    placeholder: "Nom du gardien",
    icon: Hand,
  },
];

function useConfetti(enabled: boolean) {
  const fired = useRef(false);

  useEffect(() => {
    if (!enabled || fired.current) return;
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    fired.current = true;
    let cancelled = false;
    const timers: number[] = [];

    void import("canvas-confetti").then(({ default: confetti }) => {
      if (cancelled) return;
      const colors = ["#EACB74", "#FFFFFF", "#2F6BFF", "#8B5CF6"];

      confetti({ particleCount: 90, spread: 78, origin: { y: 0.34 }, colors, disableForReducedMotion: true });

      [260, 520].forEach((delay, index) => {
        timers.push(
          window.setTimeout(() => {
            confetti({
              particleCount: 60,
              angle: index === 0 ? 62 : 118,
              spread: 62,
              origin: { x: index === 0 ? 0 : 1, y: 0.62 },
              colors,
              disableForReducedMotion: true,
            });
          }, delay),
        );
      });
    });

    return () => {
      cancelled = true;
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [enabled]);
}

function StatCard({
  icon: Icon,
  label,
  value,
  detail,
  delay,
}: {
  icon: typeof Trophy;
  label: string;
  value: string;
  detail?: string;
  delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="glass p-4"
    >
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="size-3.5 shrink-0" />
        <p className="eyebrow">{label}</p>
      </div>
      <p className="tabular mt-2 font-display text-xl font-bold tracking-tight">{value}</p>
      {detail ? <p className="mt-0.5 truncate text-xs text-muted-foreground">{detail}</p> : null}
    </motion.div>
  );
}

export function ChampionStage() {
  const tournament = useTournament();
  const teams = useTeamMap();
  const setAward = useTournamentStore((state) => state.setAward);

  const championId = tournament ? tournamentChampion(tournament.knockout) : null;
  const runnerUpId = tournament ? tournamentRunnerUp(tournament.knockout) : null;
  const semiFinalists = useMemo(
    () => (tournament ? semiFinalLosers(tournament.knockout) : []),
    [tournament],
  );

  const stats = useMemo(() => (tournament ? computeStats(tournament) : null), [tournament]);
  const teamAwards = useMemo(
    () => (tournament ? computeTeamAwards(tournament) : []),
    [tournament],
  );

  useConfetti(Boolean(championId));

  if (!tournament || !stats) return null;

  const champion = championId ? teams.get(championId) : null;
  const runnerUp = runnerUpId ? teams.get(runnerUpId) : null;

  const podium = [
    { rank: 2, teamId: runnerUpId, label: "Finaliste", height: "h-16", tone: "bg-white/10" },
    { rank: 1, teamId: championId, label: "Champion", height: "h-24", tone: "bg-champagne/25" },
    {
      rank: 3,
      teamId: semiFinalists[0] ?? null,
      secondaryId: semiFinalists[1] ?? null,
      label: semiFinalists.length > 1 ? "Demi-finalistes" : "Demi-finaliste",
      height: "h-11",
      tone: "bg-white/[0.07]",
    },
  ];

  return (
    <div className="space-y-12">
      {/* ------------------------------- The lift ------------------------------- */}
      <section className="relative overflow-hidden rounded-xl border border-champagne/25 bg-champagne/[0.05] px-5 py-12 text-center sm:py-16">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 -top-24 h-64 bg-[radial-gradient(ellipse_at_center,hsl(45_73%_66%/0.22),transparent_70%)]"
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.7, rotate: -8 }}
          animate={{ opacity: 1, scale: 1, rotate: 0 }}
          transition={{ type: "spring", stiffness: 180, damping: 18 }}
          className="relative mx-auto grid size-20 place-items-center rounded-full border border-champagne/40 bg-champagne/10"
        >
          <span aria-hidden className="absolute inset-0 animate-pulse-ring rounded-full border border-champagne/50" />
          <Trophy className="size-9 text-champagne" />
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.25 }}
          className="eyebrow mt-7 text-champagne/80"
        >
          {tournament.name}
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          className="mt-4 flex flex-col items-center gap-4"
        >
          <TeamCrest team={champion} size="xl" />
          <h2 className="text-gradient-trophy font-display text-3xl font-black tracking-tight sm:text-5xl">
            {champion?.name}
          </h2>
          <Badge variant="trophy">Champion</Badge>
        </motion.div>

        {runnerUp ? (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="mt-6 text-sm text-muted-foreground"
          >
            Finaliste malheureux : <span className="text-foreground/90">{runnerUp.name}</span>
          </motion.p>
        ) : null}
      </section>

      {/* -------------------------------- Podium -------------------------------- */}
      <section aria-labelledby="podium-title">
        <h3 id="podium-title" className="eyebrow mb-5 text-center">
          Le podium
        </h3>

        <div className="mx-auto flex max-w-lg items-end justify-center gap-3 sm:gap-5">
          {podium.map((step, index) => {
            const team = step.teamId ? teams.get(step.teamId) : null;
            const secondary =
              "secondaryId" in step && step.secondaryId ? teams.get(step.secondaryId) : null;
            if (!team) return null;

            return (
              <motion.div
                key={step.rank}
                initial={{ opacity: 0, y: 26 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.7 + index * 0.12, type: "spring", stiffness: 160, damping: 20 }}
                className="flex min-w-0 flex-1 flex-col items-center"
              >
                <TeamCrest team={team} size={step.rank === 1 ? "lg" : "md"} />
                <p
                  className={cn(
                    "mt-2 w-full truncate text-center text-xs font-medium sm:text-sm",
                    step.rank === 1 && "text-champagne",
                  )}
                >
                  {team.name}
                </p>
                {secondary ? (
                  <p className="mt-0.5 w-full truncate text-center text-[11px] text-muted-foreground">
                    &amp; {secondary.name}
                  </p>
                ) : null}

                <div
                  className={cn(
                    "mt-3 grid w-full place-items-center rounded-t-md border border-b-0 border-white/10",
                    step.height,
                    step.tone,
                  )}
                >
                  <span
                    className={cn(
                      "font-display text-lg font-black",
                      step.rank === 1 ? "text-champagne" : "text-foreground/70",
                    )}
                  >
                    {step.rank}
                  </span>
                </div>
                <p className="w-full border-t border-white/10 pt-1.5 text-center text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  {step.label}
                </p>
              </motion.div>
            );
          })}
        </div>
      </section>

      {/* --------------------------- Palmarès collectif --------------------------- */}
      {teamAwards.length > 0 ? (
        <section aria-labelledby="team-awards-title">
          <h3 id="team-awards-title" className="eyebrow mb-1.5">
            Palmarès collectif
          </h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Calculé automatiquement sur la phase de ligue, où chaque club dispute le même nombre de
            matchs. Les distinctions en doré récompensent, celles en rouge piquent un peu.
          </p>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {teamAwards.map((award, index) => {
              const team = teams.get(award.teamId);
              const wooden = award.tone === "wooden";

              return (
                <motion.div
                  key={award.key}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(index * 0.06, 0.5), duration: 0.4 }}
                  className={cn(
                    "glass surface-sheen relative overflow-hidden p-4",
                    wooden ? "border-white/10" : "border-champagne/20",
                  )}
                >
                  <span
                    aria-hidden
                    className={cn(
                      "absolute inset-y-0 left-0 w-0.5 bg-gradient-to-b",
                      wooden ? "from-rose/60 to-rose/5" : "from-champagne/80 to-champagne/10",
                    )}
                  />
                  <div
                    className={cn(
                      "flex items-center gap-2",
                      wooden ? "text-rose/80" : "text-champagne/85",
                    )}
                  >
                    {wooden ? (
                      <TrendingDown className="size-3.5 shrink-0" />
                    ) : (
                      <Award className="size-3.5 shrink-0" />
                    )}
                    <p className="eyebrow">{award.label}</p>
                  </div>

                  <div className="mt-3 flex items-center gap-3">
                    <TeamCrest team={team} size="md" />
                    <div className="min-w-0">
                      <p className="truncate font-display text-base font-bold tracking-tight">
                        {team?.name}
                      </p>
                      <p
                        className={cn(
                          "tabular text-sm",
                          wooden ? "text-rose/90" : "text-champagne",
                        )}
                      >
                        {award.value}
                      </p>
                    </div>
                  </div>

                  <p className="mt-2.5 text-xs text-muted-foreground">{award.caption}</p>
                </motion.div>
              );
            })}
          </div>
        </section>
      ) : null}

      {/* ------------------------------ Statistics ------------------------------ */}
      <section aria-labelledby="stats-title">
        <h3 id="stats-title" className="eyebrow mb-4">
          Statistiques du tournoi
        </h3>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard
            icon={Users}
            label="Matchs joués"
            value={`${stats.matchesPlayed}`}
            detail={`sur ${stats.matchesTotal} programmés`}
            delay={0.05}
          />
          <StatCard
            icon={Goal}
            label="Buts inscrits"
            value={`${stats.totalGoals}`}
            detail={`${stats.averageGoals.toFixed(2)} par match`}
            delay={0.1}
          />
          <StatCard
            icon={Flame}
            label="Plus large victoire"
            value={
              stats.biggestWin
                ? `${stats.biggestWin.winnerGoals} – ${stats.biggestWin.loserGoals}`
                : "—"
            }
            detail={
              stats.biggestWin
                ? `${teams.get(stats.biggestWin.winnerId)?.name} c. ${teams.get(stats.biggestWin.loserId)?.name} · ${stats.biggestWin.stage}`
                : undefined
            }
            delay={0.15}
          />
          <StatCard
            icon={Sparkles}
            label="Meilleure attaque"
            value={stats.bestAttack ? `${stats.bestAttack.value} buts` : "—"}
            detail={stats.bestAttack ? teams.get(stats.bestAttack.teamId)?.name : undefined}
            delay={0.2}
          />
          <StatCard
            icon={Shield}
            label="Meilleure défense"
            value={stats.bestDefense ? `${stats.bestDefense.value} encaissés` : "—"}
            detail={stats.bestDefense ? teams.get(stats.bestDefense.teamId)?.name : undefined}
            delay={0.25}
          />
          <StatCard
            icon={Medal}
            label="Clean sheets"
            value={stats.cleanSheets ? `${stats.cleanSheets.value}` : "—"}
            detail={stats.cleanSheets ? teams.get(stats.cleanSheets.teamId)?.name : undefined}
            delay={0.3}
          />
        </div>

        <p className="mt-3 text-xs text-muted-foreground">
          Attaque et défense sont mesurées sur la phase de ligue, où chaque club dispute le même
          nombre de matchs — la comparaison reste équitable.
        </p>
      </section>

      {/* ------------------------------- Distinctions --------------------------- */}
      <section aria-labelledby="awards-title">
        <h3 id="awards-title" className="eyebrow mb-1.5">
          Distinctions individuelles
        </h3>
        <p className="mb-4 text-sm text-muted-foreground">
          Ces quatre distinctions se renseignent à la main : l&apos;application enregistre les
          scores, pas les buteurs. Elles apparaissent ensuite dans l&apos;export PDF.
          Enregistrement automatique.
        </p>

        <div className="grid gap-3 sm:grid-cols-2">
          {AWARD_FIELDS.map((field, index) => {
            const value = (tournament.awards[field.key] ?? "").trim();
            const filled = value.length > 0;

            return (
              <motion.div
                key={field.key}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(index * 0.06, 0.3), duration: 0.4 }}
                className={cn(
                  "glass relative overflow-hidden p-4 transition-colors",
                  filled && "border-champagne/30 bg-champagne/[0.05]",
                )}
              >
                {filled ? (
                  <span
                    aria-hidden
                    className="pointer-events-none absolute -right-6 -top-6 size-20 rounded-full bg-champagne/10 blur-xl"
                  />
                ) : null}

                <Label htmlFor={`award-${field.key}`} className="flex items-center gap-2">
                  <field.icon
                    className={cn("size-3.5", filled ? "text-champagne" : "text-muted-foreground")}
                  />
                  {field.label}
                </Label>
                <p className="mt-0.5 text-xs text-muted-foreground">{field.caption}</p>

                <Input
                  id={`award-${field.key}`}
                  value={tournament.awards[field.key] ?? ""}
                  placeholder={field.placeholder}
                  maxLength={60}
                  onChange={(event) => setAward(field.key, event.target.value)}
                  className={cn(
                    "mt-3",
                    filled && "border-champagne/35 font-display font-bold text-champagne",
                  )}
                />
              </motion.div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
