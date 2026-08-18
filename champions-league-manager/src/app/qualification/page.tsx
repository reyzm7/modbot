"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { RefreshCw, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import { PageIntro } from "@/components/layout/page-intro";
import { StepNav } from "@/components/layout/step-nav";
import { QualificationBoard } from "@/components/tournament/qualification-board";
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
import { useTournament } from "@/hooks/use-tournament";
import { useTournamentStore } from "@/store/tournament-store";

export default function QualificationPage() {
  const tournament = useTournament();
  const lockQualification = useTournamentStore((state) => state.lockQualification);
  const resetKnockout = useTournamentStore((state) => state.resetKnockout);
  const router = useRouter();

  const locked = Boolean(tournament?.qualifiedSnapshot);

  function handleValidate() {
    if (lockQualification()) {
      toast.success("Qualification validée", { description: "Le tableau final est prêt à être tiré." });
      router.push("/knockout");
    } else {
      toast.error("Phase de ligue incomplète", {
        description: "Tous les matchs doivent être renseignés.",
      });
    }
  }

  function handleRecompute() {
    resetKnockout();
    toast.success("Phase finale réinitialisée", {
      description: "Validez de nouveau pour repartir du classement actuel.",
    });
  }

  return (
    <AppShell step="qualification">
      <PageIntro
        eyebrow="Étape 4 · Fin de la phase de ligue"
        title="Le classement a parlé"
        description="Le plateau se scinde en trois. Validez pour figer la qualification et ouvrir le tableau final."
        action={
          locked ? (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="secondary" size="sm">
                  <RefreshCw />
                  Recalculer
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Recalculer la qualification ?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Tous les tirages et résultats de la phase finale seront effacés, puis la
                    qualification repartira du classement actuel. La phase de ligue n&apos;est pas
                    touchée.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Annuler</AlertDialogCancel>
                  <AlertDialogAction onClick={handleRecompute}>
                    Effacer la phase finale
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : null
        }
      />

      <QualificationBoard />

      {!locked ? (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6, duration: 0.45 }}
          className="glass surface-sheen mt-8 flex flex-col items-center gap-4 p-8 text-center"
        >
          <Sparkles className="size-6 text-primary" />
          <div>
            <h2 className="font-display text-lg font-bold tracking-tight">
              Ouvrir la phase finale
            </h2>
            <p className="mx-auto mt-1.5 max-w-md text-sm text-muted-foreground">
              La qualification sera figée sur ce classement. Vous pourrez toujours la recalculer
              plus tard.
            </p>
          </div>
          <Button size="lg" onClick={handleValidate}>
            Valider la qualification
          </Button>
        </motion.div>
      ) : null}

      <StepNav
        backHref="/league"
        nextHref={locked ? "/knockout" : undefined}
        nextLabel="Phase finale"
        nextDisabled={!locked}
        onNext={locked ? undefined : handleValidate}
        hint={locked ? "Qualification figée." : "Validez la qualification pour continuer."}
      />
    </AppShell>
  );
}
