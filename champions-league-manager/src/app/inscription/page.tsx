"use client";

import { useState } from "react";
import { ClipboardList, ExternalLink } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SIGNUP_EMBED_URL, SIGNUP_URL } from "@/lib/links";

export default function InscriptionPage() {
  const [loaded, setLoaded] = useState(false);

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
      <header className="mb-8">
        <p className="eyebrow flex items-center gap-2">
          <ClipboardList className="size-3.5" />
          Participer
        </p>
        <h1 className="mt-3 font-display text-3xl font-black tracking-tight sm:text-4xl">
          Formulaire d&apos;inscription
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Remplissez le formulaire pour rejoindre le prochain tournoi. Pensez à lire le{" "}
          <Link href="/reglement" className="text-primary underline-offset-4 hover:underline">
            règlement
          </Link>{" "}
          au préalable.
        </p>
      </header>

      <div className="glass relative overflow-hidden">
        {!loaded ? (
          <div className="absolute inset-0 z-10 grid place-items-center bg-background/40 p-6">
            <div className="w-full max-w-md space-y-3">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-4 w-2/3" />
              <p className="pt-2 text-center text-xs text-muted-foreground">
                Chargement du formulaire…
              </p>
            </div>
          </div>
        ) : null}

        <iframe
          src={SIGNUP_EMBED_URL}
          title="Formulaire d'inscription"
          onLoad={() => setLoaded(true)}
          className="h-[78vh] min-h-[540px] w-full border-0"
        />
      </div>

      <div className="mt-4">
        <Button asChild variant="secondary" size="sm">
          <a href={SIGNUP_URL} target="_blank" rel="noopener noreferrer">
            <ExternalLink />
            Ouvrir le formulaire dans un nouvel onglet
          </a>
        </Button>
      </div>

      <p className="mt-6 text-xs text-muted-foreground">
        Le formulaire est hébergé par Google : vos réponses lui sont transmises directement, et ce
        site n&apos;y a pas accès.
      </p>
    </main>
  );
}
