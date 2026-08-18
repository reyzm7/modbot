import { NextResponse } from "next/server";

import { ADMIN_COOKIE, SESSION_COOKIE_OPTIONS, checkAdminCode, createSessionToken } from "@/lib/auth";

export async function POST(request: Request) {
  let code = "";
  try {
    const body = (await request.json()) as { code?: unknown };
    code = typeof body.code === "string" ? body.code : "";
  } catch {
    return NextResponse.json({ error: "Requête invalide." }, { status: 400 });
  }

  if (!process.env.ADMIN_CODE || !process.env.ADMIN_SESSION_SECRET) {
    return NextResponse.json(
      { error: "Le serveur n'est pas configuré : ADMIN_CODE ou ADMIN_SESSION_SECRET manquant." },
      { status: 500 },
    );
  }

  if (!checkAdminCode(code)) {
    // Freine les tentatives automatisées sans gêner un humain.
    await new Promise((resolve) => setTimeout(resolve, 600));
    return NextResponse.json({ error: "Code incorrect." }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set(ADMIN_COOKIE, await createSessionToken(), SESSION_COOKIE_OPTIONS);
  return response;
}
