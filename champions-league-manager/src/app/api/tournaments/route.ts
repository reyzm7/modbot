import { NextResponse } from "next/server";

import { isAdmin } from "@/lib/auth";
import { isPublished, tournamentStatus, type TournamentSummary } from "@/lib/remote";
import { isPlayed } from "@/lib/standings";
import { TABLE, adminSupabase } from "@/lib/supabase";
import type { Tournament } from "@/lib/types";
import { slugify } from "@/lib/utils";

export const dynamic = "force-dynamic";

type Row = {
  slug: string;
  name: string;
  logo: string | null;
  status: string;
  published: boolean;
  updated_at: string;
  data: Tournament;
};

function toSummary(row: Row): TournamentSummary {
  return {
    slug: row.slug,
    name: row.name,
    logo: row.logo,
    status: tournamentStatus(row.data),
    published: row.published,
    teamCount: row.data.teams?.length ?? 0,
    playedMatches: (row.data.league?.matches ?? []).filter(isPlayed).length,
    totalMatches: (row.data.league?.matches ?? []).length,
    updatedAt: row.updated_at,
  };
}

export async function GET() {
  const admin = await isAdmin();

  try {
    const supabase = adminSupabase();
    let query = supabase
      .from(TABLE)
      .select("slug, name, logo, status, published, updated_at, data")
      .order("updated_at", { ascending: false })
      .limit(100);

    if (!admin) query = query.eq("published", true);

    const { data, error } = await query;
    if (error) throw error;

    return NextResponse.json({
      admin,
      tournaments: ((data ?? []) as Row[]).map(toSummary),
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erreur inconnue.", tournaments: [], admin },
      { status: 500 },
    );
  }
}

export async function POST(request: Request) {
  if (!(await isAdmin())) {
    return NextResponse.json({ error: "Accès réservé à l'administrateur." }, { status: 401 });
  }

  let tournament: Tournament;
  try {
    const body = (await request.json()) as { tournament?: Tournament };
    if (!body.tournament) throw new Error("tournoi manquant");
    tournament = body.tournament;
  } catch {
    return NextResponse.json({ error: "Requête invalide." }, { status: 400 });
  }

  try {
    const supabase = adminSupabase();
    const base = slugify(tournament.name) || "tournoi";

    // Quelques essais suffisent : le suffixe aléatoire rend la collision très improbable.
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const suffix = Math.random().toString(36).slice(2, 6);
      const slug = `${base}-${suffix}`.slice(0, 60);
      const payload = { ...tournament, slug };

      const { error } = await supabase.from(TABLE).insert({
        slug,
        name: tournament.name,
        logo: tournament.logo ?? null,
        status: tournamentStatus(payload),
        published: isPublished(payload),
        data: payload,
      });

      if (!error) return NextResponse.json({ slug });
      if (error.code !== "23505") throw error;
    }

    throw new Error("Impossible de générer une adresse unique.");
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erreur inconnue." },
      { status: 500 },
    );
  }
}
