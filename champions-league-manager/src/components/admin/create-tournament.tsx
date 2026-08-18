"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { LogoPicker } from "@/components/tournament/logo-picker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clampInt } from "@/lib/utils";
import { useTournamentStore } from "@/store/tournament-store";

const PRESETS = [8, 16, 24, 32, 36];

export function CreateTournament({ onCreated }: { onCreated?: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [teamCount, setTeamCount] = useState(16);
  const [logo, setLogo] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  const createTournament = useTournamentStore((state) => state.createTournament);
  const loadTournament = useTournamentStore((state) => state.loadTournament);

  async function submit() {
    if (name.trim().length < 2 || busy) return;
    setBusy(true);

    try {
      createTournament({ name: name.trim(), logo, teamCount: clampInt(teamCount, 8, 36) });
      const draft = useTournamentStore.getState().tournament;
      if (!draft) throw new Error("Création impossible.");

      const response = await fetch("/api/tournaments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tournament: draft }),
      });
      const body = (await response.json()) as { slug?: string; error?: string };
      if (!response.ok || !body.slug) throw new Error(body.error ?? "Enregistrement refusé.");

      loadTournament({ ...draft, slug: body.slug });
      setOpen(false);
      setName("");
      setLogo(undefined);
      onCreated?.();
      toast.success("Tournoi créé", { description: "Renseignez les équipes pour l'ouvrir au public." });
      router.push("/setup");
    } catch (error) {
      toast.error("Création impossible", {
        description: error instanceof Error ? error.message : "Erreur inconnue.",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus />
          Créer un tournoi
        </Button>
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouveau tournoi</DialogTitle>
          <DialogDescription>
            Il restera privé tant que toutes les équipes ne sont pas renseignées.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-4">
          <div>
            <Label>Logo du tournoi <span className="text-muted-foreground">(facultatif)</span></Label>
            <div className="mt-2">
              <LogoPicker
                value={logo}
                onChange={setLogo}
                onClear={() => setLogo(undefined)}
                label="Logo du tournoi"
                size="lg"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="new-name">Nom du tournoi</Label>
            <Input
              id="new-name"
              value={name}
              maxLength={60}
              placeholder="Coupe MrDarryl"
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void submit();
              }}
              className="mt-2"
            />
          </div>

          <div>
            <Label htmlFor="new-count">Nombre d&apos;équipes</Label>
            <div className="mt-2 flex flex-wrap gap-2">
              {PRESETS.map((preset) => (
                <Button
                  key={preset}
                  type="button"
                  size="sm"
                  variant={teamCount === preset ? "default" : "secondary"}
                  onClick={() => setTeamCount(preset)}
                >
                  {preset}
                </Button>
              ))}
              <Input
                id="new-count"
                type="number"
                min={8}
                max={36}
                step={2}
                value={teamCount}
                onChange={(event) => setTeamCount(Number(event.target.value) || 16)}
                className="h-9 w-20"
              />
            </div>
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <Button onClick={() => void submit()} disabled={busy || name.trim().length < 2}>
            {busy ? "Création…" : "Créer"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
