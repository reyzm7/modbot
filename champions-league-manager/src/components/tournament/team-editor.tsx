"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, ClipboardPaste, Circle } from "lucide-react";
import { toast } from "sonner";

import { LogoPicker } from "@/components/tournament/logo-picker";
import { TeamCrest } from "@/components/tournament/team-crest";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useTournament } from "@/hooks/use-tournament";
import { useTournamentStore } from "@/store/tournament-store";

export function TeamEditor() {
  const tournament = useTournament();
  const updateTeam = useTournamentStore((state) => state.updateTeam);
  const clearTeamLogo = useTournamentStore((state) => state.clearTeamLogo);
  const [bulk, setBulk] = useState("");
  const [bulkOpen, setBulkOpen] = useState(false);

  const grouped = useMemo(() => {
    if (!tournament) return [];
    const pots = new Map<number, typeof tournament.teams>();
    for (const team of tournament.teams) {
      pots.set(team.pot, [...(pots.get(team.pot) ?? []), team]);
    }
    return [...pots.entries()].sort((a, b) => a[0] - b[0]);
  }, [tournament]);

  if (!tournament) return null;

  const named = tournament.teams.filter((team) => team.name.trim().length > 0).length;

  function applyBulk() {
    if (!tournament) return;
    const lines = bulk
      .split(/\r?\n|,|;/)
      .map((line) => line.trim())
      .filter(Boolean);

    if (lines.length === 0) {
      toast.error("Rien à importer", { description: "Saisissez un nom par ligne." });
      return;
    }

    tournament.teams.forEach((team, index) => {
      if (index < lines.length) updateTeam(team.id, { name: lines[index].slice(0, 40) });
    });

    const filled = Math.min(lines.length, tournament.teams.length);
    toast.success(`${filled} équipe${filled > 1 ? "s" : ""} importée${filled > 1 ? "s" : ""}`, {
      description:
        lines.length > tournament.teams.length
          ? `${lines.length - tournament.teams.length} nom(s) en trop ont été ignorés.`
          : "Les logos restent à ajouter, un par un.",
    });
    setBulk("");
    setBulkOpen(false);
  }

  return (
    <section aria-labelledby="teams-heading">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="teams-heading" className="font-display text-lg font-semibold tracking-tight">
            Les équipes
          </h2>
          <p className="text-sm text-muted-foreground">
            {named} / {tournament.teams.length} renseignées · le logo est facultatif
          </p>
        </div>

        <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
          <DialogTrigger asChild>
            <Button variant="secondary" size="sm">
              <ClipboardPaste />
              Coller une liste
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Importer les noms d&apos;équipes</DialogTitle>
              <DialogDescription>
                Un nom par ligne. Les {tournament.teams.length} premiers remplissent la grille dans
                l&apos;ordre, ce qui fixe aussi les chapeaux.
              </DialogDescription>
            </DialogHeader>

            <Label htmlFor="bulk-teams" className="sr-only">
              Liste des équipes
            </Label>
            <textarea
              id="bulk-teams"
              value={bulk}
              onChange={(event) => setBulk(event.target.value)}
              rows={9}
              placeholder={"Real Madrid\nManchester City\nBayern Munich\n…"}
              className="w-full rounded-md border border-white/12 bg-white/[0.04] p-3 text-sm text-foreground placeholder:text-muted-foreground/70 focus-visible:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            />

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="secondary">Annuler</Button>
              </DialogClose>
              <Button onClick={applyBulk}>Remplir la grille</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-6">
        {grouped.map(([pot, teams]) => (
          <div key={pot}>
            <p className="eyebrow mb-2.5">
              Chapeau {pot} · {teams.length} équipes
            </p>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {teams.map((team) => {
                const filled = team.name.trim().length > 0;
                return (
                  <motion.div
                    key={team.id}
                    layout
                    className="glass flex items-center gap-3 p-2.5"
                  >
                    <span className="grid w-6 shrink-0 place-items-center font-display text-xs font-bold text-muted-foreground">
                      {team.seed}
                    </span>

                    <TeamCrest team={team} size="sm" />

                    <div className="min-w-0 flex-1">
                      <Label htmlFor={`team-${team.id}`} className="sr-only">
                        Nom de l&apos;équipe {team.seed}
                      </Label>
                      <Input
                        id={`team-${team.id}`}
                        value={team.name}
                        maxLength={40}
                        placeholder={`Équipe ${team.seed}`}
                        onChange={(event) => updateTeam(team.id, { name: event.target.value })}
                        className="h-9 border-transparent bg-transparent px-2 hover:border-white/12"
                      />
                    </div>

                    <LogoPicker
                      label={`Logo de ${team.name || `l'équipe ${team.seed}`}`}
                      value={team.logo}
                      onChange={(logo) => updateTeam(team.id, { logo })}
                      onClear={() => clearTeamLogo(team.id)}
                    />

                    {filled ? (
                      <CheckCircle2 className="size-4 shrink-0 text-mint" aria-label="Renseignée" />
                    ) : (
                      <Circle className="size-4 shrink-0 text-white/20" aria-label="À renseigner" />
                    )}
                  </motion.div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
