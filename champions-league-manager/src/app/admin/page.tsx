"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ExternalLink, Eye, EyeOff, LogOut, Settings2, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { AdminLogin } from "@/components/admin/admin-login";
import { CreateTournament } from "@/components/admin/create-tournament";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { adminLogout, useAdminSession, useAdminStore } from "@/hooks/use-admin";
import { STATUS_LABEL, type TournamentSummary } from "@/lib/remote";
import type { Tournament } from "@/lib/types";
import { useTournamentStore } from "@/store/tournament-store";

function when(iso: string): string {
  try {
    return new Date(iso).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export default function AdminPage() {
  const { admin, checked } = useAdminSession();
  const mode = useAdminStore((state) => state.mode);
  const setMode = useAdminStore((state) => state.setMode);
  const [tournaments, setTournaments] = useState<TournamentSummary[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const router = useRouter();
  const loadTournament = useTournamentStore((state) => state.loadTournament);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/tournaments", { cache: "no-store" });
      const body = (await response.json()) as { tournaments?: TournamentSummary[]; error?: string };
      if (body.error) throw new Error(body.error);
      setTournaments(body.tournaments ?? []);
    } catch (error) {
      toast.error("Chargement impossible", {
        description: error instanceof Error ? error.message : "Erreur inconnue.",
      });
      setTournaments([]);
    }
  }, []);

  useEffect(() => {
    if (admin) void refresh();
  }, [admin, refresh]);

  async function manage(slug: string) {
    setBusy(slug);
    try {
      const response = await fetch(`/api/tournaments/${slug}`, { cache: "no-store" });
      const body = (await response.json()) as { tournament?: Tournament; error?: string };
      if (!response.ok || !body.tournament) throw new Error(body.error ?? "Tournoi introuvable.");
      loadTournament({ ...body.tournament, slug });
      router.push("/setup");
    } catch (error) {
      toast.error("Ouverture impossible", {
        description: error instanceof Error ? error.message : "Erreur inconnue.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function remove(slug: string, name: string) {
    setBusy(slug);
    try {
      const response = await fetch(`/api/tournaments/${slug}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Suppression refusée.");
      toast.success("Tournoi supprimé", { description: name });
      await refresh();
    } catch (error) {
      toast.error("Suppression impossible", {
        description: error instanceof Error ? error.message : "Erreur inconnue.",
      });
    } finally {
      setBusy(null);
    }
  }

  if (!checked) {
    return (
      <main className="mx-auto w-full max-w-4xl space-y-4 px-4 py-12 sm:px-6">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-40 w-full" />
      </main>
    );
  }

  if (admin && mode === "visitor") {
    return (
      <main className="mx-auto w-full max-w-md px-4 py-24 text-center sm:px-6">
        <Eye className="mx-auto size-8 text-muted-foreground" />
        <h1 className="mt-5 font-display text-2xl font-bold tracking-tight">Mode visiteur</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Vous voyez le site comme le voit votre public. Repassez en mode administrateur pour
          gérer vos tournois.
        </p>
        <Button size="lg" className="mt-6" onClick={() => setMode("admin")}>
          <ShieldCheck />
          Repasser en administrateur
        </Button>
      </main>
    );
  }

  if (!admin) {
    return (
      <main className="mx-auto w-full max-w-md px-4 py-24 text-center sm:px-6">
        <ShieldCheck className="mx-auto size-8 text-primary" />
        <h1 className="mt-5 font-display text-2xl font-bold tracking-tight">Espace administrateur</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Connectez-vous pour créer et gérer les tournois. Les visiteurs n&apos;ont pas besoin de
          compte pour suivre la compétition.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <AdminLogin trigger={<Button size="lg">Se connecter</Button>} />
          <Button asChild variant="ghost" size="lg">
            <Link href="/">Retour</Link>
          </Button>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Administration</p>
          <h1 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">
            Vos tournois
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <CreateTournament onCreated={() => void refresh()} />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              void adminLogout().then(() => router.push("/"));
            }}
          >
            <LogOut />
            Déconnexion
          </Button>
        </div>
      </header>

      {tournaments === null ? (
        <div className="space-y-2">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : tournaments.length === 0 ? (
        <div className="glass p-10 text-center">
          <p className="font-display text-lg font-bold">Aucun tournoi pour l&apos;instant</p>
          <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
            Créez-en un : il restera invisible pour les visiteurs jusqu&apos;à ce que toutes les
            équipes soient renseignées.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {tournaments.map((tournament, index) => (
            <motion.li
              key={tournament.slug}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(index * 0.04, 0.3) }}
              className="glass flex flex-wrap items-center gap-3 p-4"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="truncate font-display text-base font-bold tracking-tight">
                    {tournament.name}
                  </h2>
                  <Badge variant="neutral">{STATUS_LABEL[tournament.status]}</Badge>
                  {tournament.published ? (
                    <Badge variant="success">
                      <Eye className="size-3" />
                      Public
                    </Badge>
                  ) : (
                    <Badge variant="danger">
                      <EyeOff className="size-3" />
                      Privé
                    </Badge>
                  )}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {tournament.teamCount} équipes · modifié le {when(tournament.updatedAt)}
                </p>
              </div>

              <div className="flex shrink-0 items-center gap-1.5">
                {tournament.published ? (
                  <Button asChild variant="ghost" size="sm">
                    <Link href={`/t/${tournament.slug}`} target="_blank">
                      <ExternalLink />
                      Voir
                    </Link>
                  </Button>
                ) : null}

                <Button
                  size="sm"
                  variant="secondary"
                  disabled={busy === tournament.slug}
                  onClick={() => void manage(tournament.slug)}
                >
                  <Settings2 />
                  Gérer
                </Button>

                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="ghost" size="icon-sm" aria-label={`Supprimer ${tournament.name}`}>
                      <Trash2 className="text-rose" />
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Supprimer « {tournament.name} » ?</AlertDialogTitle>
                      <AlertDialogDescription>
                        Le tournoi, ses résultats et son classement seront définitivement effacés.
                        Les visiteurs perdront immédiatement l&apos;accès à la page. Cette action est
                        irréversible.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Annuler</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => void remove(tournament.slug, tournament.name)}
                      >
                        Supprimer définitivement
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </motion.li>
          ))}
        </ul>
      )}
    </main>
  );
}
