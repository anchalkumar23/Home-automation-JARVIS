/** Login/logout/status calls against the session-cookie-based auth backend. */

export async function checkAuthStatus(backendUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${backendUrl}/api/auth/status`, { credentials: "include" })
    if (!res.ok) return false
    const data = await res.json()
    return Boolean(data.authenticated)
  } catch {
    return false
  }
}

export async function login(backendUrl: string, password: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch(`${backendUrl}/api/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      return { ok: false, error: data.detail || "Login failed." }
    }
    return { ok: true }
  } catch {
    return { ok: false, error: "Couldn't reach the backend." }
  }
}

export async function logout(backendUrl: string): Promise<void> {
  try {
    await fetch(`${backendUrl}/api/auth/logout`, { method: "POST", credentials: "include" })
  } catch {
    // best-effort — the cookie will just expire on its own if this fails
  }
}
