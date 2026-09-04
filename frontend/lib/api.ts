/**
 * Interim shared-secret gate for the backend API, ahead of proper auth (see
 * docs/superpowers/specs/2026-09-05-interim-auth-patches.md). The key is
 * necessarily visible in the browser bundle since these calls run client-side
 * — it stops anonymous internet scanners, not a targeted attacker who has
 * already loaded the site. Real per-user auth replaces this later.
 */
export const JARVIS_API_KEY = process.env.NEXT_PUBLIC_JARVIS_API_KEY ?? ""

export function apiHeaders(extra?: Record<string, string>): Record<string, string> {
  return { "X-Jarvis-Key": JARVIS_API_KEY, ...extra }
}
