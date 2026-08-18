import { cookies } from "next/headers";

export const ADMIN_COOKIE = "mrd_admin";
const MAX_AGE_SECONDS = 60 * 60 * 12;

function secret(): string {
  const value = process.env.ADMIN_SESSION_SECRET;
  if (!value) throw new Error("ADMIN_SESSION_SECRET manquant.");
  return value;
}

function toBase64Url(bytes: ArrayBuffer | Uint8Array): string {
  const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let binary = "";
  view.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function sign(payload: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret()),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload));
  return toBase64Url(signature);
}

/** Comparaison à durée constante : ne renseigne pas l'attaquant sur l'avancement. */
function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let index = 0; index < a.length; index += 1) {
    diff |= a.charCodeAt(index) ^ b.charCodeAt(index);
  }
  return diff === 0;
}

export function checkAdminCode(code: string): boolean {
  const expected = process.env.ADMIN_CODE;
  if (!expected) return false;
  return safeEqual(code, expected);
}

export async function createSessionToken(): Promise<string> {
  const expiry = Date.now() + MAX_AGE_SECONDS * 1000;
  const payload = `admin.${expiry}`;
  return `${payload}.${await sign(payload)}`;
}

export async function verifySessionToken(token: string | undefined): Promise<boolean> {
  if (!token) return false;
  const parts = token.split(".");
  if (parts.length !== 3) return false;
  const [role, expiry, signature] = parts;
  if (role !== "admin") return false;
  const expiresAt = Number(expiry);
  if (!Number.isFinite(expiresAt) || expiresAt < Date.now()) return false;
  return safeEqual(signature, await sign(`${role}.${expiry}`));
}

export async function isAdmin(): Promise<boolean> {
  try {
    const store = await cookies();
    return await verifySessionToken(store.get(ADMIN_COOKIE)?.value);
  } catch {
    return false;
  }
}

export const SESSION_COOKIE_OPTIONS = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  maxAge: MAX_AGE_SECONDS,
};
