"use client";

import { useState, type ReactNode } from "react";
import { KeyRound, LogIn } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAdminStore } from "@/hooks/use-admin";

export function AdminLogin({ trigger }: { trigger?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const setAdmin = useAdminStore((state) => state.setAdmin);

  async function submit() {
    if (!code.trim() || busy) return;
    setBusy(true);
    try {
      const response = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      const body = (await response.json()) as { error?: string };

      if (!response.ok) {
        toast.error("Connexion refusée", { description: body.error ?? "Code incorrect." });
        return;
      }

      setAdmin(true);
      setCode("");
      setOpen(false);
      toast.success("Connecté en administrateur");
    } catch {
      toast.error("Connexion impossible", { description: "Vérifiez votre réseau." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="ghost" size="sm">
            <KeyRound />
            Espace admin
          </Button>
        )}
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connexion administrateur</DialogTitle>
          <DialogDescription>
            Réservé à l&apos;organisateur. Les visiteurs consultent les tournois sans se connecter.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4">
          <Label htmlFor="admin-code">Code d&apos;administration</Label>
          <Input
            id="admin-code"
            type="password"
            autoComplete="current-password"
            value={code}
            placeholder="••••••••"
            onChange={(event) => setCode(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void submit();
            }}
            className="mt-2"
          />
        </div>

        <div className="mt-5 flex justify-end">
          <Button onClick={() => void submit()} disabled={busy || !code.trim()}>
            <LogIn />
            {busy ? "Vérification…" : "Se connecter"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
