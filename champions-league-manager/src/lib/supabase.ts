import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * Tolère les erreurs de saisie fréquentes : espaces, guillemets collés depuis
 * un fichier, protocole oublié, barre oblique finale.
 */
function normalizeUrl(raw: string | undefined): string | null {
  if (!raw) return null;
  const cleaned = raw.trim().replace(/^["']|["']$/g, "").replace(/\/+$/, "");
  if (!cleaned) return null;
  const withProtocol = /^https?:\/\//i.test(cleaned) ? cleaned : `https://${cleaned}`;
  try {
    return new URL(withProtocol).origin;
  } catch {
    return null;
  }
}

const rawUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const url = normalizeUrl(rawUrl);
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim();

/**
 * Client navigateur, clé publique. Renvoie null si la configuration manque :
 * l'interface bascule alors sur une actualisation périodique au lieu de casser.
 */
export function browserSupabase(): SupabaseClient | null {
  if (!url || !anonKey) return null;
  return createClient(url, anonKey, {
    auth: { persistSession: false },
    realtime: { params: { eventsPerSecond: 5 } },
  });
}

/** Client serveur, clé de service. Ne doit jamais être importé côté navigateur. */
export function adminSupabase(): SupabaseClient {
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY?.trim();

  if (!rawUrl) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_URL est absente. Ajoutez-la dans Vercel → Settings → Environment Variables, puis redéployez.",
    );
  }
  if (!url) {
    throw new Error(
      `NEXT_PUBLIC_SUPABASE_URL n'est pas une adresse valide (reçu : « ${rawUrl.slice(0, 40)} »). ` +
        "Elle doit ressembler à https://abcdefgh.supabase.co — copiez le champ Project URL dans Supabase → Settings → General.",
    );
  }
  if (!serviceKey) {
    throw new Error(
      "SUPABASE_SERVICE_ROLE_KEY est absente. Copiez la clé service_role depuis Supabase → Settings → API Keys.",
    );
  }
  return createClient(url, serviceKey, { auth: { persistSession: false } });
}

export const TABLE = "tournaments";
