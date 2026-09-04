"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { AudioLines, BellRing, Keyboard, Mail, Mic, Power, SendHorizonal, Volume2, VolumeX } from "lucide-react"
import { ArcReactor } from "@/components/arc-reactor"
import { ClockPanel, StatusPanel, SystemPanel } from "@/components/hud-panels"
import {
  BusinessReportCard,
  CalendarEventDeleteConfirm,
  CalendarEventDraftCard,
  type ClientAction,
  ContentDraftCard,
  EmailDraftCard,
  FileUploadCard,
  HighlightDetectionResultCard,
  ImageModal,
  InlineImage,
  ReadSourceTag,
  type SearchResult,
  SearchSourcesCard,
  SilenceRemovalResultCard,
  SubtitleResultCard,
  TypewriterText,
} from "@/components/message-cards"
import { VoiceVisualizer } from "@/components/voice-visualizer"
import { apiHeaders } from "@/lib/api"
import { useSpeech } from "@/lib/use-speech"
import { useWakeWord } from "@/lib/use-wake-word"
import { useTaskReminders } from "@/lib/use-task-reminders"
import { cn } from "@/lib/utils"

/* ── Types ──────────────────────────────────────────────────────────────── */

type OrbState = "idle" | "listening" | "thinking" | "speaking"

interface ToolUsed {
  name: string
  arguments?: Record<string, unknown>
  result?: unknown
  ok: boolean
  error?: string | null
}

interface BackendResponse {
  answer: string
  provider: string
  model?: string | null
  tools_used?: ToolUsed[]
  action?: ClientAction | null
  error?: string | null
  image_url?: string | null
  language?: string
}

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  provider?: string
  model?: string | null
  toolsUsed?: ToolUsed[]
  action?: ClientAction | null
  imageUrl?: string | null
}

/* ── Constants ──────────────────────────────────────────────────────────── */

const BACKEND_URL = process.env.NEXT_PUBLIC_JARVIS_BACKEND ?? "http://127.0.0.1:8000"

const SOURCE_TOOL_NAMES = new Set([
  "web_search",
  "get_news",
  "search_youtube",
  "search_papers",
  "search_patents",
])

const STATE_COPY: Record<OrbState, string> = {
  idle: "Ready when you are",
  listening: "Listening...",
  thinking: "Processing...",
  speaking: "Responding...",
}

const FILLER_PHRASES = [
  "One moment, sir…",
  "Working on that…",
  "Let me look into it…",
  "Processing your request…",
  "Give me a second…",
  "Checking now…",
  "On it…",
  "Analyzing…",
  "Running the query…",
  "Just a moment…",
]

function randomFiller(): string {
  return FILLER_PHRASES[Math.floor(Math.random() * FILLER_PHRASES.length)]
}

/* ── Backend API call ──────────────────────────────────────────────────── */

async function sendToBackend(
  message: string,
  history: { role: "user" | "assistant"; content: string }[],
): Promise<BackendResponse> {
  const response = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      message,
      history: history.map((h) => ({ role: h.role, content: h.content })),
      provider: "auto",
      user_id: "default",
    }),
  })
  if (!response.ok) {
    throw new Error(`Backend ${response.status}: ${response.statusText}`)
  }
  return response.json()
}

function offlineFallback(input: string): BackendResponse {
  const text = input.toLowerCase()
  let answer: string
  if (/\b(hi|hello|hey|greetings)\b/.test(text)) {
    answer =
      "Hello. I'm running in offline mode — the backend appears unreachable. Basic conversation is available."
  } else if (text.includes("time")) {
    answer = `It's currently ${new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}. Note: I'm running offline.`
  } else if (text.includes("status") || text.includes("diagnostic") || text.includes("system")) {
    answer =
      "I'm operating in offline fallback mode. The backend server at " +
      BACKEND_URL +
      " is unreachable. Please start the backend to unlock full capabilities."
  } else {
    answer = `I've received your message, but I'm currently unable to reach the backend at ${BACKEND_URL}. Please ensure the Python server is running, then try again.`
  }
  return { answer, provider: "offline_fallback", tools_used: [] }
}

/* ── Component ──────────────────────────────────────────────────────────── */

export function JarvisInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [orbState, setOrbState] = useState<OrbState>("idle")
  const [booted, setBooted] = useState(false)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [fillerText, setFillerText] = useState("")
  const [typingMsgId, setTypingMsgId] = useState<string | null>(null)
  const [fullscreenImage, setFullscreenImage] = useState<string | null>(null)
  const [gmailConnected, setGmailConnected] = useState<boolean | null>(null)
  const [gmailEmail, setGmailEmail] = useState<string | null>(null)
  const [sendingEmail, setSendingEmail] = useState(false)
  const [savingCalendarEvent, setSavingCalendarEvent] = useState(false)
  const [deletingCalendarEvent, setDeletingCalendarEvent] = useState(false)

  const {
    supported,
    listening,
    startListening,
    stopListening,
    speak,
    cancelSpeech,
    voices,
    selectedVoiceURI,
    setSelectedVoiceURI,
    muted,
    setMuted,
    micLevelsRef,
  } = useSpeech()

  const { wakeWordSupported, wakeWordActive, startWakeWordDetection, stopWakeWordDetection } =
    useWakeWord()

  const { remindersEnabled, enableReminders, disableReminders } = useTaskReminders(BACKEND_URL)

  const stateRef = useRef<OrbState>("idle")
  stateRef.current = orbState
  const messagesRef = useRef<Message[]>([])
  messagesRef.current = messages
  const scrollRef = useRef<HTMLDivElement>(null)

  // Boot animation
  useEffect(() => {
    const t = setTimeout(() => setBooted(true), 120)
    return () => clearTimeout(t)
  }, [])

  // Check backend health on mount
  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        const res = await fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(4000) })
        if (!cancelled) setBackendOnline(res.ok)
      } catch {
        if (!cancelled) setBackendOnline(false)
      }
    }
    check()
    return () => {
      cancelled = true
    }
  }, [])

  // Check Gmail connection status on mount
  useEffect(() => {
    let cancelled = false
    async function checkGmail() {
      try {
        const res = await fetch(`${BACKEND_URL}/api/gmail/status`, { headers: apiHeaders() })
        if (!res.ok) return
        const data = await res.json()
        if (!cancelled) {
          setGmailConnected(Boolean(data.connected))
          setGmailEmail(data.email ?? null)
        }
      } catch {
        if (!cancelled) setGmailConnected(false)
      }
    }
    checkGmail()
    return () => {
      cancelled = true
    }
  }, [])

  // Auto-scroll comms log
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, orbState, fillerText])

  // ── Send message handler ────────────────────────────────────────────
  const handleSend = useCallback(
    async (raw: string) => {
      const content = raw.trim()
      if (!content) return
      setInput("")

      // Interrupt current speech if speaking
      if (stateRef.current === "speaking") {
        cancelSpeech()
      }

      const userMsg: Message = { id: crypto.randomUUID(), role: "user", content }
      setMessages((prev) => [...prev, userMsg])
      setOrbState("thinking")
      setFillerText(randomFiller())

      // Build history for the backend (last 12 messages)
      const currentMessages = messagesRef.current
      const history = [...currentMessages, userMsg]
        .filter((m) => m.role === "user" || m.role === "assistant")
        .slice(-12)
        .map((m) => ({ role: m.role, content: m.content }))

      let response: BackendResponse
      try {
        response = await sendToBackend(content, history)
        setBackendOnline(true)
      } catch {
        response = offlineFallback(content)
        setBackendOnline(false)
      }

      setFillerText("")

      // Handle client-side actions from backend
      if (response.action?.type === "open_url" && response.action.url) {
        try {
          const a = document.createElement("a")
          a.href = response.action.url
          a.target = "_blank"
          a.rel = "noopener noreferrer"
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
        } catch {
          // Link will be in the chat
        }
      }

      const msgId = crypto.randomUUID()
      const assistantMsg: Message = {
        id: msgId,
        role: "assistant",
        content: response.answer,
        provider: response.provider,
        model: response.model,
        toolsUsed: response.tools_used,
        action: response.action,
        imageUrl: response.image_url,
      }
      setMessages((prev) => [...prev, assistantMsg])
      setTypingMsgId(msgId)

      if (!muted && supported) {
        setOrbState("speaking")
        speak(response.answer, () => setOrbState("idle"), response.language)
      } else {
        setOrbState("idle")
      }
    },
    [speak, supported, muted, cancelSpeech],
  )

  // ── Shared comms-log system message helper ─────────────────────────
  const pushSystemMessage = useCallback((content: string) => {
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant" as const, content }])
  }, [])

  // ── Voice input error handler ────────────────────────────────────────
  const handleVoiceError = useCallback(
    (message: string) => {
      setOrbState("idle")
      pushSystemMessage(message)
    },
    [pushSystemMessage],
  )

  // ── Gmail connect + send handlers ───────────────────────────────────
  const handleConnectGmail = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/gmail/auth-url`, { headers: apiHeaders() })
      if (!res.ok) throw new Error()
      const data = await res.json()
      if (data.url) window.open(data.url, "_blank", "noopener,noreferrer")
    } catch {
      pushSystemMessage(
        "Couldn't start the Gmail connection — check that the backend is configured with Google OAuth credentials.",
      )
    }
  }, [pushSystemMessage])

  const handleSendViaGmail = useCallback(
    async (to: string, subject: string, body: string) => {
      if (!to.trim()) {
        pushSystemMessage("Please enter a recipient email address before sending.")
        return
      }
      setSendingEmail(true)
      try {
        const res = await fetch(`${BACKEND_URL}/api/gmail/send`, {
          method: "POST",
          headers: apiHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ to, subject, body }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || "Gmail send failed.")
        }
        pushSystemMessage(`Email sent to ${to} via Gmail.`)
      } catch (err) {
        pushSystemMessage(err instanceof Error ? err.message : "Couldn't send the email via Gmail.")
      } finally {
        setSendingEmail(false)
      }
    },
    [pushSystemMessage],
  )

  // ── Calendar create/edit/delete handlers ────────────────────────────
  const handleSaveCalendarEvent = useCallback(
    async (
      eventId: string | undefined,
      summary: string,
      start: string,
      end: string,
      description: string,
      location: string,
      attendees: string[],
    ) => {
      if (!summary.trim() || !start || !end) {
        pushSystemMessage("Event title, start, and end time are required before saving.")
        return
      }
      setSavingCalendarEvent(true)
      try {
        const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
        const res = await fetch(
          eventId ? `${BACKEND_URL}/api/calendar/events/${eventId}` : `${BACKEND_URL}/api/calendar/events`,
          {
            method: eventId ? "PATCH" : "POST",
            headers: apiHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({
              summary,
              start,
              end,
              description,
              location,
              attendees,
              time_zone: timeZone,
            }),
          },
        )
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || "Could not save the calendar event.")
        }
        pushSystemMessage(
          eventId ? `Updated "${summary}" on your calendar.` : `Created "${summary}" on your calendar.`,
        )
      } catch (err) {
        pushSystemMessage(err instanceof Error ? err.message : "Could not save the calendar event.")
      } finally {
        setSavingCalendarEvent(false)
      }
    },
    [pushSystemMessage],
  )

  const handleDeleteCalendarEvent = useCallback(
    async (eventId: string) => {
      setDeletingCalendarEvent(true)
      try {
        const res = await fetch(`${BACKEND_URL}/api/calendar/events/${eventId}`, {
          method: "DELETE",
          headers: apiHeaders(),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || "Could not delete the calendar event.")
        }
        pushSystemMessage("Event deleted from your calendar.")
      } catch (err) {
        pushSystemMessage(err instanceof Error ? err.message : "Could not delete the calendar event.")
      } finally {
        setDeletingCalendarEvent(false)
      }
    },
    [pushSystemMessage],
  )

  const handleCancelCalendarDelete = useCallback(() => {
    pushSystemMessage("Cancelled — the event was not deleted.")
  }, [pushSystemMessage])

  const handleToggleReminders = useCallback(async () => {
    if (remindersEnabled) {
      disableReminders()
      pushSystemMessage("Reminders turned off.")
    } else {
      const ok = await enableReminders()
      pushSystemMessage(
        ok
          ? "Reminders are on — I'll notify you here in the browser when a task's due time arrives, as long as this tab stays open."
          : "Couldn't enable reminders — notification permission was denied or isn't available in this browser.",
      )
    }
  }, [remindersEnabled, enableReminders, disableReminders, pushSystemMessage])

  // ── Mic toggle ─────────────────────────────────────────────────────
  const toggleMic = useCallback(() => {
    if (!supported) return
    if (listening) {
      stopListening()
      setOrbState("idle")
      return
    }
    cancelSpeech()
    setOrbState("listening")
    startListening((text) => {
      setOrbState("thinking")
      handleSend(text)
    }, handleVoiceError)
  }, [supported, listening, stopListening, cancelSpeech, startListening, handleSend, handleVoiceError])

  // Reset orb when recognition ends externally
  useEffect(() => {
    if (!listening && stateRef.current === "listening") setOrbState("idle")
  }, [listening])

  // ── Keyboard shortcuts: Ctrl+J / Alt+J ──────────────────────────────
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.altKey) && e.key.toLowerCase() === "j") {
        e.preventDefault()
        if (stateRef.current === "speaking") {
          cancelSpeech()
          setOrbState("idle")
        }
        if (stateRef.current === "listening") {
          stopListening()
          setOrbState("idle")
        } else if (stateRef.current === "idle") {
          cancelSpeech()
          setOrbState("listening")
          startListening((text) => {
            setOrbState("thinking")
            handleSend(text)
          }, handleVoiceError)
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [stopListening, cancelSpeech, startListening, handleSend, handleVoiceError])

  // ── Wake word ────────────────────────────────────────────────────────
  const toggleWakeWord = useCallback(() => {
    if (wakeWordActive) {
      stopWakeWordDetection()
    } else {
      startWakeWordDetection(() => {
        if (stateRef.current === "idle") {
          stopWakeWordDetection()
          cancelSpeech()
          setOrbState("listening")
          startListening((text) => {
            setOrbState("thinking")
            handleSend(text)
          }, handleVoiceError)
        }
      }, handleVoiceError)
    }
  }, [
    wakeWordActive,
    startWakeWordDetection,
    stopWakeWordDetection,
    cancelSpeech,
    startListening,
    handleSend,
    handleVoiceError,
  ])

  /* ── Render helpers ─────────────────────────────────────────────────── */

  const comms: Message[] = messages.length
    ? messages
    : [
        {
          id: "boot",
          role: "assistant" as const,
          content:
            "Good day. All systems are online and operating within nominal parameters. How may I assist you?",
        },
      ]

  const providerLabel = (msg: Message) => {
    if (!msg.provider) return null
    const parts: string[] = []
    if (msg.provider && msg.provider !== "offline_fallback") parts.push(msg.provider)
    if (msg.model) parts.push(msg.model)
    return parts.length ? parts.join(" · ") : null
  }

  const toolsLabel = (msg: Message) => {
    if (!msg.toolsUsed?.length) return null
    return msg.toolsUsed.map((t) => (t.ok ? `✓ ${t.name}` : `✗ ${t.name}`)).join(", ")
  }

  const searchSources = (msg: Message): SearchResult[] => {
    const calls = msg.toolsUsed?.filter((t) => SOURCE_TOOL_NAMES.has(t.name) && t.ok) ?? []
    const all = calls.flatMap((call) => {
      const results = (call.result as { results?: SearchResult[] } | undefined)?.results
      return Array.isArray(results) ? results : []
    })
    const seen = new Set<string>()
    return all.filter((result) => {
      if (seen.has(result.url)) return false
      seen.add(result.url)
      return true
    })
  }

  const readSourceUrl = (msg: Message): string | null => {
    const call = msg.toolsUsed?.find((t) => t.name === "read_url_content" && t.ok)
    const url = (call?.result as { url?: string } | undefined)?.url
    return typeof url === "string" ? url : null
  }

  return (
    <main className="hud-grid relative h-screen overflow-y-auto bg-background text-foreground lg:overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 hud-vignette" />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 hud-scanlines" />

      {fullscreenImage && (
        <ImageModal src={fullscreenImage} onClose={() => setFullscreenImage(null)} />
      )}

      <div
        className={cn(
          "relative z-10 mx-auto flex min-h-screen w-full max-w-[1440px] flex-col px-4 py-3 transition-all duration-700 sm:px-6 lg:h-screen lg:min-h-0 lg:px-8",
          booted ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0",
        )}
      >
        {/* ── Header ──────────────────────────────────────────────── */}
        <header className="shrink-0 flex items-center justify-between border-b border-primary/20 pb-3">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-md border border-primary/35 bg-primary/10 text-primary shadow-[0_0_18px_color-mix(in_oklch,var(--primary)_30%,transparent)]">
              <Power className="h-4 w-4" aria-hidden="true" />
            </span>
            <div>
              <p className="font-mono text-xl font-semibold leading-none tracking-[0.22em] text-primary text-glow sm:text-2xl">
                JARVIS
              </p>
              <p className="mt-1 hidden font-mono text-[9px] uppercase tracking-[0.45em] text-muted-foreground sm:block">
                Just A Rather Very Intelligent System
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <span
              className="hidden items-center gap-2 font-mono text-[10px] uppercase tracking-[0.35em] sm:flex"
              style={{ color: backendOnline === false ? "var(--destructive)" : "var(--primary)" }}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{
                  backgroundColor:
                    backendOnline === false ? "var(--destructive)" : "var(--primary)",
                  boxShadow: `0 0 12px ${backendOnline === false ? "var(--destructive)" : "var(--primary)"}`,
                }}
              />
              {backendOnline === null ? "Checking" : backendOnline ? "Online" : "Offline"}
            </span>

            {voices.length > 0 && (
              <select
                id="voice-select"
                value={selectedVoiceURI}
                onChange={(e) => setSelectedVoiceURI(e.target.value)}
                className="hidden h-9 max-w-[140px] truncate rounded-md border border-primary/25 bg-card/50 px-2 font-mono text-[10px] uppercase tracking-[0.1em] text-primary backdrop-blur-md focus:outline-none sm:block"
                aria-label="Select voice"
              >
                {voices.map((v) => (
                  <option key={v.voiceURI} value={v.voiceURI}>
                    {v.name}
                  </option>
                ))}
              </select>
            )}

            <button
              id="mute-toggle"
              onClick={() => {
                if (!muted) cancelSpeech()
                setMuted((m) => !m)
              }}
              className={cn(
                "flex h-9 items-center gap-2 rounded-md border px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors",
                !muted
                  ? "border-primary/35 bg-primary/10 text-primary"
                  : "border-border bg-card/35 text-muted-foreground hover:text-foreground",
              )}
              aria-pressed={!muted}
              aria-label={muted ? "Unmute voice" : "Mute voice"}
            >
              {muted ? (
                <VolumeX className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <Volume2 className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              <span className="hidden sm:inline">{muted ? "Muted" : "Voice"}</span>
            </button>

            {wakeWordSupported && (
              <button
                id="wake-word-toggle"
                onClick={toggleWakeWord}
                className={cn(
                  "flex h-9 items-center gap-2 rounded-md border px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors",
                  wakeWordActive
                    ? "border-accent/40 bg-accent/15 text-accent"
                    : "border-border bg-card/35 text-muted-foreground hover:text-foreground",
                )}
                aria-pressed={wakeWordActive}
                title={'Say "Jarvis" to activate'}
              >
                <AudioLines className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="hidden sm:inline">Wake</span>
              </button>
            )}

            <button
              id="google-toggle"
              onClick={handleConnectGmail}
              disabled={gmailConnected === null}
              className={cn(
                "flex h-9 items-center gap-2 rounded-md border px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors",
                gmailConnected
                  ? "border-primary/35 bg-primary/10 text-primary hover:bg-primary/20"
                  : "border-border bg-card/35 text-muted-foreground hover:text-foreground",
              )}
              title={
                gmailConnected
                  ? `Connected as ${gmailEmail ?? "unknown"} (Mail + Calendar) — click to reconnect`
                  : "Connect Google to send email and read your calendar"
              }
            >
              <Mail className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">{gmailConnected ? "Google" : "Connect Google"}</span>
            </button>

            <button
              id="reminders-toggle"
              onClick={handleToggleReminders}
              className={cn(
                "flex h-9 items-center gap-2 rounded-md border px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors",
                remindersEnabled
                  ? "border-accent/40 bg-accent/15 text-accent"
                  : "border-border bg-card/35 text-muted-foreground hover:text-foreground",
              )}
              aria-pressed={remindersEnabled}
              title={
                remindersEnabled
                  ? "Reminders on — click to turn off"
                  : "Enable browser notifications for due tasks (only while this tab is open)"
              }
            >
              <BellRing className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">Reminders</span>
            </button>
          </div>
        </header>

        {/* ── Main grid ────────────────────────────────────────────── */}
        <section className="grid min-h-0 flex-1 grid-cols-1 gap-4 py-4 lg:grid-cols-[280px_minmax(320px,1fr)_360px] lg:gap-6 lg:overflow-hidden">
          <aside className="order-2 space-y-4 lg:order-1 lg:min-h-0 lg:overflow-hidden lg:pt-3">
            <SystemPanel />
            <StatusPanel />
            <div className="rounded-lg border border-primary/15 bg-card/30 p-3 backdrop-blur-sm">
              <h3 className="mb-2 font-mono text-[10px] tracking-[0.3em] text-muted-foreground">
                SHORTCUTS
              </h3>
              <ul className="space-y-1.5 font-mono text-[10px] text-muted-foreground">
                <li className="flex items-center gap-2">
                  <Keyboard className="h-3 w-3 text-primary" aria-hidden="true" />
                  <span>
                    <kbd className="rounded border border-primary/25 bg-primary/10 px-1.5 py-0.5 text-primary">
                      Ctrl+J
                    </kbd>{" "}
                    Voice input
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  <Keyboard className="h-3 w-3 text-primary" aria-hidden="true" />
                  <span>
                    <kbd className="rounded border border-primary/25 bg-primary/10 px-1.5 py-0.5 text-primary">
                      Alt+J
                    </kbd>{" "}
                    Voice input
                  </span>
                </li>
              </ul>
            </div>
          </aside>

          {/* ── Center: ARC reactor ─────────────────────────────────── */}
          <section className="order-1 flex min-h-[420px] flex-col items-center justify-center lg:order-2 lg:min-h-0 lg:overflow-hidden">
            <div className="w-full max-w-[520px] shrink-0">
              <ClockPanel />
            </div>
            <div className="relative mt-4 flex min-h-0 w-full flex-1 items-center justify-center">
              <div aria-hidden="true" className="absolute h-[72%] w-px bg-primary/15" />
              <div aria-hidden="true" className="absolute h-px w-[72%] bg-primary/15" />
              <ArcReactor state={orbState} className="w-[min(42vh,380px)] max-w-[380px]" />
            </div>
            <div className="mt-2 w-full max-w-[320px] shrink-0">
              <VoiceVisualizer state={orbState} levelsRef={micLevelsRef} />
              <p className="mt-1 text-center font-mono text-[10px] uppercase tracking-[0.42em] text-primary text-glow">
                {STATE_COPY[orbState]}
              </p>
            </div>
          </section>

          {/* ── Comms Log ───────────────────────────────────────────── */}
          <aside className="order-3 flex min-h-[360px] flex-col rounded-lg border border-primary/20 bg-card/35 p-4 shadow-hud backdrop-blur-md lg:mt-3 lg:min-h-0 lg:overflow-hidden">
            <div className="mb-3 flex shrink-0 items-center justify-between">
              <div>
                <h2 className="font-mono text-[10px] uppercase tracking-[0.35em] text-muted-foreground">
                  Comms Log
                </h2>
                <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.35em] text-muted-foreground">
                  J.A.R.V.I.S
                </p>
              </div>
              <span className="font-mono text-[9px] uppercase tracking-[0.28em] text-primary">
                {muted ? "Muted" : "Voice on"}
              </span>
            </div>
            <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
              {comms.map((message) => (
                <article
                  key={message.id}
                  className={cn(
                    "animate-rise rounded-lg border px-4 py-3 font-mono text-xs leading-relaxed",
                    message.role === "user"
                      ? "ml-auto max-w-[82%] border-accent/30 bg-accent/10 text-foreground"
                      : "mr-auto max-w-[88%] border-primary/35 bg-primary/10 text-card-foreground shadow-[0_0_24px_color-mix(in_oklch,var(--primary)_12%,transparent)]",
                  )}
                >
                  <p className="mb-2 text-[9px] uppercase tracking-[0.32em] text-muted-foreground">
                    {message.role === "user" ? "Operator" : "J.A.R.V.I.S"}
                  </p>

                  {/* Typewriter effect for the latest assistant message */}
                  {message.role === "assistant" && message.id === typingMsgId ? (
                    <TypewriterText text={message.content} onDone={() => setTypingMsgId(null)} />
                  ) : (
                    message.content
                  )}

                  {/* Generated image inline with loading state */}
                  {message.imageUrl && (
                    <InlineImage
                      src={message.imageUrl}
                      onFullscreen={() => setFullscreenImage(message.imageUrl!)}
                    />
                  )}

                  {/* Clickable link for open_url actions */}
                  {message.action?.type === "open_url" && message.action.url && (
                    <a
                      href={message.action.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 block truncate text-[11px] text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
                    >
                      🔗 {message.action.url}
                    </a>
                  )}

                  {/* Email draft: recipient input + real send + mailto fallback + copy buttons */}
                  {message.action?.type === "compose_email" && (
                    <EmailDraftCard
                      action={message.action}
                      onSend={handleSendViaGmail}
                      sending={sendingEmail}
                    />
                  )}

                  {/* Calendar event draft: create or edit, pending confirmation */}
                  {message.action?.type === "calendar_event_draft" && (
                    <CalendarEventDraftCard
                      action={message.action}
                      onSave={handleSaveCalendarEvent}
                      saving={savingCalendarEvent}
                    />
                  )}

                  {/* Calendar event deletion: pending confirmation */}
                  {message.action?.type === "calendar_event_delete_confirm" && (
                    <CalendarEventDeleteConfirm
                      action={message.action}
                      onConfirm={handleDeleteCalendarEvent}
                      onCancel={handleCancelCalendarDelete}
                      deleting={deletingCalendarEvent}
                    />
                  )}

                  {/* Business report: structured research summary */}
                  {message.action?.type === "business_report" && (
                    <BusinessReportCard action={message.action} />
                  )}

                  {/* Drafted content: social caption, script, or marketing copy */}
                  {message.action?.type === "content_draft" && (
                    <ContentDraftCard action={message.action} />
                  )}

                  {/* Subtitle generation result */}
                  {message.action?.type === "subtitle_result" && (
                    <SubtitleResultCard action={message.action} />
                  )}

                  {/* Silence removal result */}
                  {message.action?.type === "silence_removal_result" && (
                    <SilenceRemovalResultCard action={message.action} />
                  )}

                  {/* Highlight detection result */}
                  {message.action?.type === "highlight_detection_result" && (
                    <HighlightDetectionResultCard action={message.action} />
                  )}

                  {/* File upload prompt for video-editing tools */}
                  {message.action?.type === "file_upload_request" && (
                    <FileUploadCard
                      action={message.action}
                      backendUrl={BACKEND_URL}
                      onUploaded={(filePath, fileName) =>
                        handleSend(`Uploaded video: ${fileName} at ${filePath}`)
                      }
                    />
                  )}

                  {/* Web search sources, if this reply used web_search */}
                  {message.role === "assistant" && (
                    <SearchSourcesCard results={searchSources(message)} />
                  )}

                  {/* Which URL was read, if this reply used read_url_content */}
                  {message.role === "assistant" && (
                    <ReadSourceTag url={readSourceUrl(message)} />
                  )}

                  {/* Provider + tools metadata */}
                  {message.role === "assistant" &&
                    (providerLabel(message) || toolsLabel(message)) && (
                      <div className="mt-2 border-t border-primary/15 pt-2 text-[9px] tracking-[0.2em] text-muted-foreground/70">
                        {providerLabel(message) && (
                          <span className="mr-3">⚡ {providerLabel(message)}</span>
                        )}
                        {toolsLabel(message) && <span>🔧 {toolsLabel(message)}</span>}
                      </div>
                    )}
                </article>
              ))}

              {/* Thinking indicator with filler phrase */}
              {orbState === "thinking" && (
                <article className="mr-auto max-w-[88%] animate-rise rounded-lg border border-primary/35 bg-primary/10 px-4 py-3 font-mono text-xs text-card-foreground">
                  <p className="mb-2 text-[9px] uppercase tracking-[0.32em] text-muted-foreground">
                    J.A.R.V.I.S
                  </p>
                  {fillerText && (
                    <p className="mb-2 italic text-muted-foreground/80">{fillerText}</p>
                  )}
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
                  </span>
                </article>
              )}
            </div>
          </aside>
        </section>

        {/* ── Input bar ─────────────────────────────────────────────── */}
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSend(input)
          }}
          className="mb-0 flex shrink-0 items-center gap-3 rounded-lg border border-primary/25 bg-card/50 p-2 shadow-hud backdrop-blur-md"
        >
          <button
            type="button"
            onClick={toggleMic}
            disabled={!supported}
            aria-label={listening ? "Stop listening" : "Start voice input"}
            className={cn(
              "flex h-11 w-11 shrink-0 items-center justify-center rounded-md border transition-colors",
              listening
                ? "border-primary bg-primary text-primary-foreground"
                : "border-primary/25 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-40",
            )}
          >
            <Mic className="h-[18px] w-[18px]" />
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              listening
                ? "Listening..."
                : supported
                  ? "Speak or type a command..."
                  : "Type a command..."
            }
            className="min-w-0 flex-1 bg-transparent font-mono text-sm text-foreground placeholder:text-muted-foreground/70 focus:outline-none"
            aria-label="Message Jarvis"
          />
          <button
            type="submit"
            disabled={!input.trim()}
            aria-label="Send message"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-30"
          >
            <SendHorizonal className="h-[18px] w-[18px]" />
          </button>
        </form>
        {!supported && (
          <p className="pb-2 text-center font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Voice input requires microphone access and browser audio support. Text input is
            always available.
          </p>
        )}
      </div>
    </main>
  )
}
