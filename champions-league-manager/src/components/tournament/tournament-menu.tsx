"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Download, FileSpreadsheet, FileText, RotateCcw, Settings2, Trash2 } from "lucide-react";
import { toast } from "sonner";

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
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useTournament } from "@/hooks/use-tournament";
import { useTournamentStore } from "@/store/tournament-store";

export function TournamentMenu() {
  const tournament = useTournament();
  const resetTournament = useTournamentStore((state) => state.resetTournament);
  const clearLeagueScores = useTournamentStore((state) => state.clearLeagueScores);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<"pdf" | "csv" | null>(null);
  const router = useRouter();

  if (!tournament) return null;

  async function handlePdf() {
    if (!tournament) return;
    setBusy("pdf");
    try {
      // jsPDF is heavy, so it is only fetched when an export is actually asked for.
      const { exportTournamentPdf } = await import("@/lib/export");
      exportTournamentPdf(tournament);
      toast.success("PDF exporté", { description: "Le rapport complet est dans vos téléchargements." });
    } catch {
      toast.error("Export PDF impossible", { description: "Réessayez dans un instant." });
    } finally {
      setBusy(null);
    }
  }

  async function handleCsv() {
    if (!tournament) return;
    setBusy("csv");
    try {
      const { exportTournamentCsv } = await import("@/lib/export");
      exportTournamentCsv(tournament);
      toast.success("CSV exporté", { description: "Classement et résultats inclus." });
    } catch {
      toast.error("Export CSV impossible", { description: "Réessayez dans un instant." });
    } finally {
      setBusy(null);
    }
  }

  function handleReset() {
    resetTournament();
    setOpen(false);
    toast.success("Tournoi supprimé", { description: "Vous pouvez en créer un nouveau." });
    router.push("/");
  }

  function handleClearScores() {
    clearLeagueScores();
    setOpen(false);
    toast.success("Scores effacés", { description: "La phase de ligue repart de zéro." });
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="secondary" size="icon-sm" aria-label="Options du tournoi">
          <Settings2 />
        </Button>
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Options du tournoi</DialogTitle>
          <DialogDescription>
            Exportez vos données ou repartez de zéro. Tout est enregistré sur cet appareil.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-2">
          <Button variant="secondary" className="justify-start" onClick={() => void handlePdf()} disabled={busy !== null}>
            <FileText />
            {busy === "pdf" ? "Génération du PDF…" : "Exporter en PDF"}
          </Button>

          <Button variant="secondary" className="justify-start" onClick={() => void handleCsv()} disabled={busy !== null}>
            <FileSpreadsheet />
            Exporter en CSV
          </Button>

          <div className="my-1 h-px bg-white/10" />

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" className="justify-start">
                <RotateCcw />
                Effacer tous les scores
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Effacer tous les scores ?</AlertDialogTitle>
                <AlertDialogDescription>
                  Les affiches de la phase de ligue sont conservées, mais chaque résultat sera remis
                  à zéro. Le classement redeviendra vierge.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Annuler</AlertDialogCancel>
                <AlertDialogAction onClick={handleClearScores}>Effacer les scores</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" className="justify-start text-rose hover:text-rose">
                <Trash2 />
                Supprimer le tournoi
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Supprimer « {tournament.name} » ?</AlertDialogTitle>
                <AlertDialogDescription>
                  Équipes, tirage, résultats et phase finale seront définitivement perdus. Exportez
                  d&apos;abord un PDF si vous voulez en garder une trace.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Annuler</AlertDialogCancel>
                <AlertDialogAction onClick={handleReset}>Supprimer définitivement</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>

        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <Download className="size-3.5" />
          Les exports reprennent le classement, tous les résultats et les statistiques.
        </p>
      </DialogContent>
    </Dialog>
  );
}
