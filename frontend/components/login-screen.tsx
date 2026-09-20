"use client"

import { useState, type FormEvent } from "react"
import { Lock, Power } from "lucide-react"
import { Button } from "@/components/ui/button"
import { login } from "@/lib/api"

export function LoginScreen({
  backendUrl,
  onSuccess,
}: {
  backendUrl: string
  onSuccess: () => void
}) {
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!password) return
    setSubmitting(true)
    setError(null)
    const result = await login(backendUrl, password)
    setSubmitting(false)
    if (result.ok) {
      onSuccess()
    } else {
      setError(result.error ?? "Login failed.")
      setPassword("")
    }
  }

  return (
    <main className="hud-grid relative flex h-screen items-center justify-center bg-background text-foreground">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 hud-vignette" />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 hud-scanlines" />

      <form
        onSubmit={handleSubmit}
        className="relative z-10 flex w-full max-w-xs flex-col items-center gap-6 rounded-lg border border-primary/20 bg-background/60 p-8 shadow-[0_0_30px_color-mix(in_oklch,var(--primary)_15%,transparent)]"
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-md border border-primary/35 bg-primary/10 text-primary shadow-[0_0_18px_color-mix(in_oklch,var(--primary)_30%,transparent)]">
          <Power className="h-5 w-5" aria-hidden="true" />
        </span>
        <p className="font-mono text-xl font-semibold tracking-[0.22em] text-primary text-glow">JARVIS</p>

        <div className="flex w-full items-center gap-2 rounded-md border border-primary/20 bg-background/80 px-3 py-2">
          <Lock className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            type="password"
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className="w-full bg-transparent font-mono text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
        </div>

        {error && (
          <p className="font-mono text-xs text-destructive" role="alert">
            {error}
          </p>
        )}

        <Button type="submit" disabled={submitting || !password} className="w-full">
          {submitting ? "Verifying…" : "Unlock"}
        </Button>
      </form>
    </main>
  )
}
