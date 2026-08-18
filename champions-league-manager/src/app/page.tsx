"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, ClipboardList, FileText, LayoutDashboard, Radio, Trophy } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SocialLinks } from "@/components/layout/social-links";
import { Skeleton } from "@/components/ui/skeleton";
import { useIsAdminActive } from "@/hooks/use-admin";
import { STATUS_LABEL, type TournamentSummary } from "@/lib/remote";

export default function HomePage() {
  const admin = useIsAdminActive();
  const checked = true;
  const [tournaments, setTournaments] = useState<TournamentSummary[] | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/tournaments", { cache: "no-store" });
      const body = (await response.json()) as { tournaments?: TournamentSummary[] };
      setTournaments(body.tournaments ?? []);
    } catch {
      setTournaments([]);
    }
  }, []);

  useEffect(() => {
    void load();

    let cancelled = false;
    let poll = window.setInterval(() => void load(), 10_000);
    let teardown: (() => void) | null = null;

    // Un tournoi qui vient d'être ouvert doit apparaître sans recharger la page.
    void import("@/lib/supabase").then(({ browserSupabase, TABLE }) => {
      if (cancelled) return;
      const supabase = browserSupabase();
      if (!supabase) return;

      window.clearInterval(poll);
      poll = window.setInterval(() => void load(), 60_000);

      const channel = supabase
        .channel("liste-tournois")
        .on("postgres_changes", { event: "*", schema: "public", table: TABLE }, () => {
          void load();
        })
        .subscribe();

      teardown = () => {
        void supabase.removeChannel(channel);
      };
    });

    return () => {
      cancelled = true;
      window.clearInterval(poll);
      teardown?.();
    };
  }, [load]);

  const visible = tournaments?.filter((tournament) => tournament.published) ?? [];

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
      <motion.header
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="relative text-center"
      >
        <div
          aria-hidden
          className="hero-beam pointer-events-none absolute left-1/2 top-[-140px] h-[380px] w-[620px] max-w-[130vw] -translate-x-1/2"
        />

        <div className="relative">
          <span className="relative mx-auto grid size-16 place-items-center rounded-2xl border border-white/12 bg-white/[0.05] shadow-glow">
            <span aria-hidden className="absolute inset-0 animate-pulse-ring rounded-2xl border border-primary/40" />
            <Trophy className="size-7 text-primary" />
          </span>

          <p className="eyebrow mt-7">Format Ligue des Champions</p>

          <h1 className="mt-3 font-display text-[2.6rem] font-black leading-[0.94] tracking-[-0.03em] sm:text-6xl lg:text-7xl">
            <span className="text-gradient">Les tournois</span>
            <br />
            <span className="text-foreground">de MrDarryl</span>
          </h1>

          <p className="mx-auto mt-6 max-w-lg text-sm leading-relaxed text-muted-foreground sm:text-base">
            Affiches, scores et classement en direct — du tirage au sort jusqu&apos;au sacre.
            Aucun compte nécessaire.
          </p>
        </div>
      </motion.header>

      <section className="mt-12" aria-labelledby="tournois">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 id="tournois" className="eyebrow">
            Tournois en cours
          </h2>
          {checked && admin ? (
            <Button asChild size="sm" variant="secondary">
              <Link href="/admin">
                <LayoutDashboard />
                Tableau de bord
              </Link>
            </Button>
          ) : null}
        </div>

        {tournaments === null ? (
          <div className="space-y-2">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : visible.length === 0 ? (
          <div className="glass p-10 text-center">
            <p className="font-display text-lg font-bold">Aucun tournoi ouvert pour le moment</p>
            <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
              Revenez bientôt : dès qu&apos;une compétition démarre, elle apparaît ici et se met à
              jour toute seule.
            </p>
          </div>
        ) : (
          <ul className="space-y-3">
            {visible.map((tournament, index) => {
              const percent = tournament.totalMatches
                ? (tournament.playedMatches / tournament.totalMatches) * 100
                : 0;

              return (
                <motion.li
                  key={tournament.slug}
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(index * 0.06, 0.3), duration: 0.4 }}
                >
                  <Link
                    href={`/t/${tournament.slug}`}
                    className="glass surface-sheen card-lift block p-5 hover:border-primary/45 sm:p-6"
                  >
                    <div className="flex items-center gap-4">
                      {tournament.logo ? (
                        <img
                          src={tournament.logo}
                          alt=""
                          className="size-14 shrink-0 rounded-xl object-cover ring-1 ring-white/10 sm:size-16"
                        />
                      ) : (
                        <span className="grid size-14 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-primary/30 to-accent/20 ring-1 ring-white/10 sm:size-16">
                          <Trophy className="size-6 text-primary sm:size-7" />
                        </span>
                      )}

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="min-w-0 truncate font-display text-lg font-bold tracking-tight sm:text-2xl">
                            {tournament.name}
                          </h3>
                          {tournament.status !== "done" ? (
                            <Badge variant="success">
                              <Radio className="size-3" />
                              En direct
                            </Badge>
                          ) : (
                            <Badge variant="trophy">Terminé</Badge>
                          )}
                        </div>
                        <p className="mt-1.5 text-xs text-muted-foreground sm:text-sm">
                          {STATUS_LABEL[tournament.status]} · {tournament.teamCount} équipes
                        </p>
                      </div>

                      <span className="hidden shrink-0 items-center gap-1.5 text-sm font-medium text-primary sm:flex">
                        Ouvrir
                        <ArrowRight className="size-4" />
                      </span>
                    </div>

                    {tournament.totalMatches > 0 ? (
                      <div className="mt-5">
                        <div className="mb-2 flex items-baseline justify-between gap-3">
                          <span className="eyebrow">Phase de ligue</span>
                          <span className="tabular text-xs text-muted-foreground">
                            {tournament.playedMatches} / {tournament.totalMatches} matchs joués
                          </span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.07]">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${percent}%` }}
                            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
                            className="h-full rounded-full bg-gradient-to-r from-primary to-accent"
                          />
                        </div>
                      </div>
                    ) : null}

                    <span className="mt-4 flex items-center justify-center gap-1.5 text-sm font-medium text-primary sm:hidden">
                      Ouvrir le tournoi
                      <ArrowRight className="size-4" />
                    </span>
                  </Link>
                </motion.li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="mt-12 grid gap-3 sm:grid-cols-2" aria-label="Participer">
        <Link
          href="/reglement"
          className="glass card-lift flex items-center gap-4 p-5 hover:border-primary/45"
        >
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-white/[0.06] ring-1 ring-white/10">
            <FileText className="size-5 text-primary" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-display text-base font-bold tracking-tight">Règlement</span>
            <span className="block text-xs text-muted-foreground">
              Les règles de la compétition
            </span>
          </span>
          <ArrowRight className="size-4 shrink-0 text-primary" />
        </Link>

        <Link
          href="/inscription"
          className="glass card-lift flex items-center gap-4 p-5 hover:border-primary/45"
        >
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-white/[0.06] ring-1 ring-white/10">
            <ClipboardList className="size-5 text-primary" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-display text-base font-bold tracking-tight">
              S&apos;inscrire
            </span>
            <span className="block text-xs text-muted-foreground">
              Rejoindre le prochain tournoi
            </span>
          </span>
          <ArrowRight className="size-4 shrink-0 text-primary" />
        </Link>
      </section>

      <SocialLinks />

    </main>
  );
}
