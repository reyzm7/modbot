"use client";

import { useEffect } from "react";
import { create } from "zustand";

export type ViewMode = "admin" | "visitor";

const MODE_KEY = "mrd-view-mode";

function storedMode(): ViewMode {
  if (typeof window === "undefined") return "admin";
  return window.localStorage.getItem(MODE_KEY) === "visitor" ? "visitor" : "admin";
}

type AdminState = {
  admin: boolean;
  checked: boolean;
  mode: ViewMode;
  setAdmin: (admin: boolean) => void;
  setMode: (mode: ViewMode) => void;
};

export const useAdminStore = create<AdminState>((set) => ({
  admin: false,
  checked: false,
  mode: "admin",
  setAdmin: (admin) => set({ admin, checked: true, mode: storedMode() }),
  setMode: (mode) => {
    if (typeof window !== "undefined") window.localStorage.setItem(MODE_KEY, mode);
    set({ mode });
  },
}));

/** Vrai seulement si l'organisateur est connecté ET n'a pas basculé en aperçu visiteur. */
export function useIsAdminActive() {
  return useAdminStore((state) => state.admin && state.mode === "admin");
}

/** Interroge le serveur une seule fois : le cookie de session n'est pas lisible en JS. */
export function useAdminSession() {
  const { admin, checked, setAdmin } = useAdminStore();

  useEffect(() => {
    if (checked) return;
    let cancelled = false;
    fetch("/api/admin/session")
      .then((response) => response.json())
      .then((body: { admin?: boolean }) => {
        if (!cancelled) setAdmin(Boolean(body.admin));
      })
      .catch(() => {
        if (!cancelled) setAdmin(false);
      });
    return () => {
      cancelled = true;
    };
  }, [checked, setAdmin]);

  return { admin, checked };
}

export async function adminLogout() {
  await fetch("/api/admin/logout", { method: "POST" });
  useAdminStore.getState().setAdmin(false);
}
