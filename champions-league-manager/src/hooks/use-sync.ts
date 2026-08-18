"use client";

import { useEffect } from "react";
import { create } from "zustand";

import { useTournament } from "@/hooks/use-tournament";
import { useTournamentStore } from "@/store/tournament-store";

type SyncState = {
  status: "idle" | "saving" | "saved" | "error";
  message: string | null;
  set: (status: SyncState["status"], message?: string | null) => void;
};

export const useSyncStore = create<SyncState>((set) => ({
  status: "idle",
  message: null,
  set: (status, message = null) => set({ status, message }),
}));

export function useSyncStatus() {
  return useSyncStore((state) => state.status);
}

/**
 * Pousse le tournoi vers le serveur après chaque modification, avec un délai
 * de grâce : saisir un score ne déclenche pas une requête par frappe.
 */
export function useAutoSave() {
  const tournament = useTournament();
  const slug = tournament?.slug;
  const updatedAt = tournament?.updatedAt;
  const setStatus = useSyncStore((state) => state.set);

  useEffect(() => {
    if (!slug || !updatedAt) return;

    const timer = setTimeout(() => {
      const current = useTournamentStore.getState().tournament;
      if (!current) return;

      setStatus("saving");
      fetch(`/api/tournaments/${slug}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tournament: current }),
      })
        .then(async (response) => {
          if (!response.ok) {
            const body = (await response.json().catch(() => ({}))) as { error?: string };
            throw new Error(body.error ?? "Enregistrement refusé.");
          }
          setStatus("saved");
        })
        .catch((error: Error) => setStatus("error", error.message));
    }, 800);

    return () => clearTimeout(timer);
  }, [slug, updatedAt, setStatus]);
}
