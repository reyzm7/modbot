import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="mx-auto grid min-h-dvh w-full max-w-lg place-items-center px-4 text-center">
      <div>
        <p className="eyebrow">Erreur 404</p>
        <h1 className="mt-3 font-display text-3xl font-bold tracking-tight">Page introuvable</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          Ce lien ne mène à aucune étape du tournoi. Revenez à l&apos;accueil pour reprendre là où
          vous en étiez.
        </p>
        <Button asChild className="mt-7">
          <Link href="/">Retour à l&apos;accueil</Link>
        </Button>
      </div>
    </main>
  );
}
