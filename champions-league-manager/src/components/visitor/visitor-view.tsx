"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Award,
  ListOrdered,
  Medal,
  Radio,
  Table2,
  TrendingDown,
  Trophy,
  Swords,
} from "lucide-react";

import { ScoreFlip } from "@/components/tournament/score-flip";
import { TeamCrest } from "@/components/tournament/team-crest";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs } from "@/components/ui/tabs";
import { knockoutWinner } from "@/lib/knockout";
import { computeTeamAwards } from "@/lib/stats";
import { STATUS_LABEL, tournamentStatus } from "@/lib/remote";
import { BAND_LABEL, computeStandings, isPlayed, qualificationBand } from "@/lib/standings";
import type { LeagueMatch, QualificationBand, Team, Tournament } from "@/lib/types";
import { cn, formatSigned } from "@/lib/utils";

const BAND_ACCENT: Record<QualificationBand, string> = {
  direct: "bg-mint",
  playoff: "bg-primary",
  out: "bg-rose/60",
};

function useTeamLookup(tournament: Tournament | null) {
  return useMemo(() => {
    const map = new Map<string, Team>();
    for (const team of tournament?.teams ?? []) map.set(team.id, team);
    return map;
  }, [tournament]);
}

/* ------------------------------- Classement ------------------------------- */

function Standings({ tournament }: { tournament: Tournament }) {
  const teams = useTeamLookup(tournament);
  const standings = useMemo(
    () => computeStandings(tournament.teams, tournament.league.matches),
    [tournament],
  );

  return (
    <div className="glass overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] border-collapse text-sm">
          <caption className="sr-only">Classement de la phase de ligue</caption>
          <thead>
            <tr className="border-b border-white/10">
              {[
                ["#", "w-10 text-center"],
                ["Club", "min-w-[150px] text-left"],
                ["J", "w-9 text-center"],
                ["G", "w-9 text-center"],
                ["N", "w-9 text-center"],
                ["P", "w-9 text-center"],
                ["BM", "hidden w-10 text-center sm:table-cell"],
                ["BE", "hidden w-10 text-center sm:table-cell"],
                ["Diff", "w-12 text-center"],
                ["Pts", "w-12 text-center"],
              ].map(([label, className]) => (
                <th
                  key={label}
                  scope="col"
                  className={cn(
                    "px-2 py-2.5 font-display text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground",
                    className,
                  )}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {standings.map((row) => {
              const band = qualificationBand(row.rank, tournament.bracketSize);
              return (
                <tr key={row.teamId} className="border-b border-white/[0.06] last:border-0">
                  <td className="relative px-2 py-2 text-center">
                    <span
                      aria-hidden
                      className={cn("absolute inset-y-1 left-0 w-0.5 rounded-full", BAND_ACCENT[band])}
                    />
                    <span className="tabular font-display text-sm font-bold">{row.rank}</span>
                  </td>
                  <td className="px-2 py-2">
                    <span className="flex items-center gap-2">
                      <TeamCrest team={teams.get(row.teamId)} size="xs" />
                      <span className="min-w-0 truncate font-medium">
                        {teams.get(row.teamId)?.name}
                      </span>
                      <span className="sr-only">{BAND_LABEL[band]}</span>
                    </span>
                  </td>
                  <td className="tabular px-2 py-2 text-center text-muted-foreground">{row.played}</td>
                  <td className="tabular px-2 py-2 text-center">{row.wins}</td>
                  <td className="tabular px-2 py-2 text-center">{row.draws}</td>
                  <td className="tabular px-2 py-2 text-center">{row.losses}</td>
                  <td className="tabular hidden px-2 py-2 text-center sm:table-cell">{row.goalsFor}</td>
                  <td className="tabular hidden px-2 py-2 text-center sm:table-cell">
                    {row.goalsAgainst}
                  </td>
                  <td
                    className={cn(
                      "tabular px-2 py-2 text-center",
                      row.goalDiff > 0 && "text-mint",
                      row.goalDiff < 0 && "text-rose",
                    )}
                  >
                    {formatSigned(row.goalDiff)}
                  </td>
                  <td className="tabular px-2 py-2 text-center font-display font-bold">
                    {row.points}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/10 px-3 py-2.5">
        {(["direct", "playoff", "out"] as const).map((band) => (
          <span key={band} className="flex items-center gap-2 text-xs text-muted-foreground">
            <span aria-hidden className={cn("h-2.5 w-0.5 rounded-full", BAND_ACCENT[band])} />
            {BAND_LABEL[band]}
          </span>
        ))}
      </div>
    </div>
  );
}

/* -------------------------------- Résultats ------------------------------- */

function ScorePill({ home, away }: { home: number | null; away: number | null }) {
  return <ScoreFlip home={home} away={away} />;
}

function Results({ tournament }: { tournament: Tournament }) {
  const teams = useTeamLookup(tournament);

  const matchdays = useMemo(() => {
    const map = new Map<number, LeagueMatch[]>();
    for (const match of tournament.league.matches) {
      map.set(match.matchday, [...(map.get(match.matchday) ?? []), match]);
    }
    return [...map.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([matchday, matches]) => ({
        matchday,
        matches: matches.sort((a, b) => a.order - b.order),
      }));
  }, [tournament]);

  if (matchdays.length === 0) {
    return (
      <p className="glass p-6 text-center text-sm text-muted-foreground">
        Le tirage n&apos;a pas encore eu lieu.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      {matchdays.map(({ matchday, matches }) => (
        <section key={matchday}>
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <h3 className="font-display text-base font-bold tracking-tight">Journée {matchday}</h3>
            <p className="tabular text-xs text-muted-foreground">
              {matches.filter(isPlayed).length} / {matches.length} joués
            </p>
          </div>
          <ul className="grid gap-2">
            {matches.map((match) => (
              <li key={match.id} className="glass flex items-center gap-2 p-2.5 sm:gap-3">
                <span className="flex min-w-0 flex-1 items-center justify-end gap-2 text-right">
                  <span className="min-w-0 truncate text-sm font-medium">
                    {teams.get(match.homeId)?.name}
                  </span>
                  <TeamCrest team={teams.get(match.homeId)} size="sm" />
                </span>
                <ScorePill home={match.homeGoals} away={match.awayGoals} />
                <span className="flex min-w-0 flex-1 items-center gap-2">
                  <TeamCrest team={teams.get(match.awayId)} size="sm" />
                  <span className="min-w-0 truncate text-sm font-medium">
                    {teams.get(match.awayId)?.name}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

/* ------------------------------ Phase finale ------------------------------ */

function Knockout({ tournament }: { tournament: Tournament }) {
  const teams = useTeamLookup(tournament);
  const drawnRounds = tournament.knockout.filter((round) => round.drawn);

  if (drawnRounds.length === 0) {
    return (
      <p className="glass p-6 text-center text-sm text-muted-foreground">
        La phase finale n&apos;a pas encore commencé.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      {drawnRounds.map((round, index) => {
        const isFinal = index === tournament.knockout.length - 1;
        return (
          <section key={round.id}>
            <h3
              className={cn(
                "mb-3 font-display text-base font-bold tracking-tight",
                isFinal && "text-champagne",
              )}
            >
              {round.name}
            </h3>
            <ul className="grid gap-2">
              {round.matches.map((match) => {
                const winner = knockoutWinner(match);
                const pens = match.homePens !== null && match.awayPens !== null;
                return (
                  <li key={match.id} className="glass p-3">
                    <div className="flex items-center gap-2 sm:gap-3">
                      <span
                        className={cn(
                          "flex min-w-0 flex-1 items-center justify-end gap-2 text-right",
                          winner === match.homeId ? "font-semibold" : "text-foreground/70",
                        )}
                      >
                        <span className="min-w-0 truncate text-sm">
                          {match.homeId ? teams.get(match.homeId)?.name : "À déterminer"}
                        </span>
                        <TeamCrest team={match.homeId ? teams.get(match.homeId) : null} size="sm" />
                      </span>
                      <ScorePill home={match.homeGoals} away={match.awayGoals} />
                      <span
                        className={cn(
                          "flex min-w-0 flex-1 items-center gap-2",
                          winner === match.awayId ? "font-semibold" : "text-foreground/70",
                        )}
                      >
                        <TeamCrest team={match.awayId ? teams.get(match.awayId) : null} size="sm" />
                        <span className="min-w-0 truncate text-sm">
                          {match.awayId ? teams.get(match.awayId)?.name : "À déterminer"}
                        </span>
                      </span>
                    </div>
                    {pens ? (
                      <p className="mt-2 text-center text-xs text-muted-foreground">
                        Tirs au but : {match.homePens} – {match.awayPens}
                      </p>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

/* --------------------------------- Palmarès -------------------------------- */

function Palmares({ tournament }: { tournament: Tournament }) {
  const teams = useTeamLookup(tournament);
  const awards = useMemo(() => computeTeamAwards(tournament), [tournament]);

  const individual = (
    [
      ["MVP du tournoi", tournament.awards.mvp],
      ["Meilleur buteur", tournament.awards.topScorer],
      ["Meilleur passeur", tournament.awards.topAssister],
      ["Meilleur gardien", tournament.awards.topKeeper ?? ""],
    ] as const
  ).filter(([, name]) => Boolean(name?.trim()));

  if (awards.length === 0 && individual.length === 0) {
    return (
      <p className="glass p-6 text-center text-sm text-muted-foreground">
        Le palmarès apparaîtra dès les premiers résultats.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      {awards.length > 0 ? (
        <section>
          <h3 className="eyebrow mb-3">Palmarès collectif</h3>
          <div className="grid gap-2 sm:grid-cols-2">
            {awards.map((award) => {
              const wooden = award.tone === "wooden";
              return (
                <div key={award.key} className="glass flex items-center gap-3 p-3.5">
                  {wooden ? (
                    <TrendingDown className="size-4 shrink-0 text-rose/80" />
                  ) : (
                    <Award className="size-4 shrink-0 text-champagne" />
                  )}
                  <TeamCrest team={teams.get(award.teamId)} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{teams.get(award.teamId)?.name}</p>
                    <p className="truncate text-xs text-muted-foreground">{award.label}</p>
                  </div>
                  <span
                    className={cn(
                      "tabular shrink-0 text-sm font-semibold",
                      wooden ? "text-rose/90" : "text-champagne",
                    )}
                  >
                    {award.value}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {individual.length > 0 ? (
        <section>
          <h3 className="eyebrow mb-3">Distinctions individuelles</h3>
          <div className="grid gap-2 sm:grid-cols-2">
            {individual.map(([label, name]) => (
              <div
                key={label}
                className="glass flex items-center gap-3 border-champagne/25 bg-champagne/[0.05] p-3.5"
              >
                <Medal className="size-4 shrink-0 text-champagne" />
                <div className="min-w-0">
                  <p className="truncate font-display text-base font-bold tracking-tight text-champagne">
                    {name}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">{label}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

/* --------------------------------- Racine --------------------------------- */

export function VisitorView({ slug }: { slug: string }) {
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const [tab, setTab] = useState("standings");

  const load = useCallback(async () => {
    try {
      const response = await fetch(`/api/tournaments/${slug}`, { cache: "no-store" });
      const body = (await response.json()) as { tournament?: Tournament; error?: string };
      if (!response.ok) throw new Error(body.error ?? "Tournoi indisponible.");
      setTournament(body.tournament ?? null);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue.");
    }
  }, [slug]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    let poll = window.setInterval(() => void load(), 8_000);
    let teardown: (() => void) | null = null;

    // Le client temps réel est lourd : la page s'affiche d'abord, il arrive ensuite.
    void import("@/lib/supabase").then(({ browserSupabase, TABLE }) => {
      if (cancelled) return;
      const supabase = browserSupabase();
      if (!supabase) return;

      // Le temps réel prend le relais : le sondage passe en simple filet de sécurité.
      window.clearInterval(poll);
      poll = window.setInterval(() => void load(), 30_000);

      const channel = supabase
        .channel(`tournoi-${slug}`)
        .on(
          "postgres_changes",
          { event: "UPDATE", schema: "public", table: TABLE, filter: `slug=eq.${slug}` },
          (payload) => {
            const next = (payload.new as { data?: Tournament }).data;
            if (next) setTournament(next);
          },
        )
        .subscribe((status) => setLive(status === "SUBSCRIBED"));

      teardown = () => {
        void supabase.removeChannel(channel);
      };
    });

    return () => {
      cancelled = true;
      window.clearInterval(poll);
      teardown?.();
    };
  }, [slug, load]);

  if (error) {
    return (
      <div className="glass mx-auto mt-16 max-w-md p-8 text-center">
        <h1 className="font-display text-lg font-bold">Tournoi indisponible</h1>
        <p className="mt-2 text-sm text-muted-foreground">{error}</p>
        <Button asChild variant="secondary" className="mt-5">
          <Link href="/">
            <ArrowLeft />
            Retour à l&apos;accueil
          </Link>
        </Button>
      </div>
    );
  }

  if (!tournament) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const status = tournamentStatus(tournament);
  const champion = tournament.knockout.length
    ? knockoutWinner(tournament.knockout[tournament.knockout.length - 1]?.matches[0])
    : null;
  const championTeam = champion ? tournament.teams.find((team) => team.id === champion) : null;

  return (
    <div>
      <motion.header
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8 flex flex-wrap items-center justify-between gap-4"
      >
        <div className="flex min-w-0 items-center gap-3">
          {tournament.logo ? (
            <img src={tournament.logo} alt="" className="size-11 rounded-lg object-cover" />
          ) : null}
          <div className="min-w-0">
            <p className="eyebrow">{STATUS_LABEL[status]}</p>
            <h1 className="mt-1 truncate font-display text-2xl font-bold tracking-tight">
              {tournament.name}
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {live ? (
            <span className="flex items-center gap-1.5 rounded-full border border-mint/30 bg-mint/10 px-2.5 py-1 text-xs text-mint">
              <Radio className="size-3 animate-pulse" />
              En direct
            </span>
          ) : null}
          <Button asChild variant="ghost" size="sm">
            <Link href="/">
              <ArrowLeft />
              Tournois
            </Link>
          </Button>
        </div>
      </motion.header>

      {championTeam ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          className="glass mb-8 flex items-center gap-4 border-champagne/30 bg-champagne/[0.06] p-5"
        >
          <Trophy className="size-7 shrink-0 text-champagne" />
          <div className="min-w-0">
            <p className="eyebrow text-champagne/80">Champion</p>
            <p className="truncate font-display text-xl font-black tracking-tight text-champagne">
              {championTeam.name}
            </p>
          </div>
        </motion.div>
      ) : null}

      <div className="mb-6">
        <Tabs
          value={tab}
          onValueChange={setTab}
          layoutId="visitor-tab"
          items={[
            { value: "standings", label: "Classement", icon: <ListOrdered className="size-4" /> },
            { value: "results", label: "Résultats", icon: <Table2 className="size-4" /> },
            { value: "knockout", label: "Phase finale", icon: <Swords className="size-4" /> },
            { value: "palmares", label: "Palmarès", icon: <Award className="size-4" /> },
          ]}
        />
      </div>

      {tab === "standings" ? <Standings tournament={tournament} /> : null}
      {tab === "results" ? <Results tournament={tournament} /> : null}
      {tab === "knockout" ? <Knockout tournament={tournament} /> : null}
      {tab === "palmares" ? <Palmares tournament={tournament} /> : null}

      <p className="mt-10 text-center text-xs text-muted-foreground">
        Page en lecture seule · mise à jour automatique
      </p>
    </div>
  );
}
