import { NextResponse } from "next/server";

import { isAdmin } from "@/lib/auth";
import { isPublished, tournamentStatus } from "@/lib/remote";
import { TABLE, adminSupabase } from "@/lib/supabase";
import type { Tournament } from "@/lib/types";

export const dynamic = "force-dynamic";

type Context = { params: Promise<{ slug: string }> };

export async function GET(_request: Request, { params }: Context) {
  const { slug } = await params;
  const admin = await isAdmin();

  try {
    const supabase = adminSupabase();
    const { data, error } = await supabase
      .from(TABLE)
      .select("slug, published, updated_at, data")
      .eq("slug", slug)
      .maybeSingle();

    if (error) throw error;
    if (!data) return NextResponse.json({ error: "Tournoi introuvable." }, { status: 404 });

    // Un tournoi encore en préparation reste invisible pour le public.
    if (!data.published && !admin) {
      return NextResponse.json({ error: "Ce tournoi n'est pas encore ouvert." }, { status: 403 });
    }

    return NextResponse.json({ tournament: data.data, updatedAt: data.updated_at, admin });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erreur inconnue." },
      { status: 500 },
    );
  }
}

export async function PUT(request: Request, { params }: Context) {
  if (!(await isAdmin())) {
    return NextResponse.json({ error: "Accès réservé à l'administrateur." }, { status: 401 });
  }

  const { slug } = await params;

  let tournament: Tournament;
  try {
    const body = (await request.json()) as { tournament?: Tournament };
    if (!body.tournament) throw new Error("tournoi manquant");
    tournament = { ...body.tournament, slug };
  } catch {
    return NextResponse.json({ error: "Requête invalide." }, { status: 400 });
  }

  try {
    const supabase = adminSupabase();
    const { error } = await supabase
      .from(TABLE)
      .update({
        name: tournament.name,
        logo: tournament.logo ?? null,
        status: tournamentStatus(tournament),
        published: isPublished(tournament),
        data: tournament,
        updated_at: new Date().toISOString(),
      })
      .eq("slug", slug);

    if (error) throw error;
    return NextResponse.json({ ok: true, published: isPublished(tournament) });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erreur inconnue." },
      { status: 500 },
    );
  }
}

export async function DELETE(_request: Request, { params }: Context) {
  if (!(await isAdmin())) {
    return NextResponse.json({ error: "Accès réservé à l'administrateur." }, { status: 401 });
  }

  const { slug } = await params;

  try {
    const supabase = adminSupabase();
    const { error } = await supabase.from(TABLE).delete().eq("slug", slug);
    if (error) throw error;
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erreur inconnue." },
      { status: 500 },
    );
  }
}
