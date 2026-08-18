"use client";

import { useState } from "react";
import { Download, ExternalLink, FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RULES_EMBED_URL, RULES_URL } from "@/lib/links";

export default function ReglementPage() {
  const [loaded, setLoaded] = useState(false);

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
      <header className="mb-8">
        <p className="eyebrow flex items-center gap-2">
          <FileText className="size-3.5" />
          Documentation
        </p>
        <h1 className="mt-3 font-display text-3xl font-black tracking-tight sm:text-4xl">
          Règlement du tournoi
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
          À lire avant de s&apos;inscrire. Le document ci-dessous fait foi en cas de litige pendant
          la compétition.
        </p>
      </header>

      <div className="glass relative overflow-hidden">
        {!loaded ? (
          <div className="absolute inset-0 z-10 grid place-items-center bg-background/40 p-6">
            <div className="w-full max-w-md space-y-3">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <p className="pt-2 text-center text-xs text-muted-foreground">
                Chargement du document…
              </p>
            </div>
          </div>
        ) : null}

        <iframe
          src={RULES_EMBED_URL}
          title="Règlement du tournoi"
          onLoad={() => setLoaded(true)}
          className="h-[70vh] min-h-[460px] w-full border-0"
          allow="autoplay"
        />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button asChild variant="secondary" size="sm">
          <a href={RULES_URL} target="_blank" rel="noopener noreferrer">
            <ExternalLink />
            Ouvrir dans un nouvel onglet
          </a>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <a href={RULES_URL} target="_blank" rel="noopener noreferrer">
            <Download />
            Télécharger
          </a>
        </Button>
      </div>

      <p className="mt-6 text-xs text-muted-foreground">
        Le document ne s&apos;affiche pas ? Il est peut-être en accès restreint sur Google Drive :
        ouvrez-le dans un nouvel onglet, ou passez son partage en « Tous les utilisateurs disposant
        du lien ».
      </p>
    </main>
  );
}
