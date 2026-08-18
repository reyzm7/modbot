"use client";

import { useEffect, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { StepRail } from "@/components/layout/step-rail";
import { TournamentMenu } from "@/components/tournament/tournament-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useAutoSave, useSyncStatus } from "@/hooks/use-sync";
import { useHydrated, useStepAccess, useTournament } from "@/hooks/use-tournament";
import { STEPS, type StepId } from "@/lib/steps";

function ShellFrame({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-5xl px-4 pb-4 pt-5 sm:px-6">{children}</div>;
}

function LoadingShell() {
  return (
    <ShellFrame>
      <div className="flex items-center gap-3">
        <Skeleton className="size-10 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3.5 w-40" />
          <Skeleton className="h-2.5 w-24" />
        </div>
      </div>
      <Skeleton className="mt-6 h-1.5 w-full rounded-full" />
      <div className="mt-10 space-y-3">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
      <span className="sr-only">Chargement du tournoi…</span>
    </ShellFrame>
  );
}

/** Témoin discret : l'organisateur doit savoir si son travail est bien parti au serveur. */
function SaveBadge() {
  const status = useSyncStatus();
  if (status === "idle") return null;

  const label =
    status === "saving" ? "Enregistrement…" : status === "saved" ? "Enregistré" : "Hors ligne";

  return (
    <span
      className={
        status === "error"
          ? "shrink-0 text-xs text-rose"
          : "shrink-0 text-xs text-muted-foreground"
      }
      role="status"
    >
      {label}
    </span>
  );
}

export function AppShell({ step, children }: { step: StepId; children: ReactNode }) {
  const hydrated = useHydrated();
  useAutoSave();
  const tournament = useTournament();
  const access = useStepAccess();
  const router = useRouter();
  const allowed = access[step];

  useEffect(() => {
    if (!hydrated) return;

    if (!tournament) {
      router.replace("/");
      return;
    }

    if (!allowed) {
      const fallback = [...STEPS].reverse().find((item) => access[item.id]) ?? STEPS[0];
      router.replace(fallback.href);
    }
  }, [hydrated, tournament, allowed, access, router]);

  if (!hydrated || !tournament || !allowed) return <LoadingShell />;

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[hsl(234_50%_4%/0.78)] backdrop-blur-xl">
        <div className="mx-auto w-full max-w-5xl px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="flex min-w-0 flex-1 items-center gap-3 rounded-md transition-opacity hover:opacity-85"
            >
              {tournament.logo ? (
                <img
                  src={tournament.logo}
                  alt=""
                  className="size-9 shrink-0 rounded-lg border border-white/12 object-contain p-0.5"
                />
              ) : (
                <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-white/12 bg-gradient-to-br from-primary/40 to-accent/30 font-display text-sm font-bold">
                  {tournament.name.trim().charAt(0).toUpperCase() || "T"}
                </span>
              )}
              <span className="min-w-0">
                <span className="block truncate font-display text-sm font-semibold tracking-tight">
                  {tournament.name}
                </span>
                <span className="block truncate text-xs text-muted-foreground">
                  {tournament.teams.length} équipes · {tournament.matchesPerTeam} matchs par équipe
                </span>
              </span>
            </Link>

            <SaveBadge />
          <TournamentMenu />
          </div>

          <div className="mt-3">
            <StepRail current={step} />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl px-4 pb-24 pt-8 sm:px-6">{children}</main>
    </div>
  );
}
