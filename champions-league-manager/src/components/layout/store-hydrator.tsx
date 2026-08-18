"use client";

import { useEffect } from "react";

import { useTournamentStore } from "@/store/tournament-store";

/**
 * Rehydration is deferred to an effect so the first client render matches the
 * server HTML exactly. Saved tournaments appear right after mount.
 */
export function StoreHydrator() {
  useEffect(() => {
    void useTournamentStore.persist.rehydrate();
  }, []);

  return null;
}
