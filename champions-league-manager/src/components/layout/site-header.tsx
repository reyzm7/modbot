"use client";

import Link from "next/link";
import {
  ClipboardList,
  Eye,
  FileText,
  Home,
  KeyRound,
  LayoutDashboard,
  LogOut,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";

import { AdminLogin } from "@/components/admin/admin-login";
import { Button } from "@/components/ui/button";
import { adminLogout, useAdminSession, useAdminStore } from "@/hooks/use-admin";
import { cn } from "@/lib/utils";

/**
 * Barre fine présente sur tout le site. Le contrôle est à gauche pour rester
 * sous les yeux de l'organisateur pendant un direct.
 */
export function SiteHeader() {
  const { admin, checked } = useAdminSession();
  const mode = useAdminStore((state) => state.mode);
  const setMode = useAdminStore((state) => state.setMode);

  if (!checked) return <div className="h-12" aria-hidden />;

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[hsl(234_50%_4%/0.85)] backdrop-blur-xl">
      <div className="mx-auto flex h-12 w-full max-w-5xl items-center gap-1.5 px-3 sm:gap-2 sm:px-6">
        {!admin ? (
          <AdminLogin
            trigger={
              <Button variant="ghost" size="sm">
                <KeyRound />
                Administrateur
              </Button>
            }
          />
        ) : (
          <>
            <div
              role="group"
              aria-label="Mode de consultation"
              className="flex items-center gap-0.5 rounded-lg border border-white/10 bg-white/[0.04] p-0.5"
            >
              <button
                type="button"
                onClick={() => setMode("admin")}
                aria-pressed={mode === "admin"}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  mode === "admin"
                    ? "bg-primary/20 text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <ShieldCheck className="size-3.5" />
                Administrateur
              </button>
              <button
                type="button"
                onClick={() => setMode("visitor")}
                aria-pressed={mode === "visitor"}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  mode === "visitor"
                    ? "bg-white/10 text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Eye className="size-3.5" />
                Visiteur
              </button>
            </div>

            {mode === "admin" ? (
              <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
                <Link href="/admin">
                  <LayoutDashboard />
                  Tableau de bord
                </Link>
              </Button>
            ) : null}
          </>
        )}

        <div className="flex-1" />

        {/* Liens publics : visibles pour tout le monde, y compris les visiteurs. */}
        <nav className="flex items-center gap-0.5" aria-label="Navigation principale">
          <Button asChild variant="ghost" size="sm" className="px-2 sm:px-3">
            <Link href="/reglement">
              <FileText />
              <span className="hidden sm:inline">Règlement</span>
            </Link>
          </Button>
          <Button asChild variant="ghost" size="sm" className="px-2 sm:px-3">
            <Link href="/inscription">
              <ClipboardList />
              <span className="hidden sm:inline">Inscription</span>
            </Link>
          </Button>
        </nav>

        <Link
          href="/"
          className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <Home className="size-4" />
          Accueil
        </Link>

        {admin ? (
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Se déconnecter"
            onClick={() => {
              void adminLogout().then(() => toast.success("Déconnecté"));
            }}
          >
            <LogOut />
          </Button>
        ) : null}
      </div>
    </header>
  );
}
