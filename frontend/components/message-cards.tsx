"use client"

import { useEffect, useRef, useState } from "react"
import { CalendarClock, Check, ClipboardCopy, Download, FileText, Loader2, Mail, Maximize2, UploadCloud, X } from "lucide-react"
import { cn } from "@/lib/utils"

/* ── Types ──────────────────────────────────────────────────────────────── */

export interface ClientAction {
  type:
    | "open_url"
    | "compose_email"
    | "calendar_event_draft"
    | "calendar_event_delete_confirm"
    | "business_report"
    | "content_draft"
    | "subtitle_result"
    | "file_upload_request"
    | "silence_removal_result"
    | "highlight_detection_result"
  url?: string
  email_to?: string
  email_subject?: string
  email_body?: string
  mailto_link?: string
  event_id?: string
  event_summary?: string
  event_start?: string
  event_end?: string
  event_description?: string
  event_location?: string
  event_attendees?: string[]
  report_topic?: string
  report_sections?: { heading: string; content: string }[]
  report_sources?: string[]
  content_topic?: string
  content_format?: string
  content_platform?: string
  content_body?: string
  content_sources?: string[]
  subtitle_file_path?: string
  subtitle_content?: string
  upload_purpose?: string
  silence_output_path?: string
  silence_original_duration?: number
  silence_new_duration?: number
  silence_removed_seconds?: number
  silence_segment_count?: number
  highlight_clips?: { path: string; start: number; end: number; reason: string }[]
}

/* ── Typewriter hook ───────────────────────────────────────────────────── */

function useTypewriter(text: string, speed = 18) {
  const [displayed, setDisplayed] = useState("")
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!text) {
      setDisplayed("")
      setDone(true)
      return
    }
    setDisplayed("")
    setDone(false)
    let i = 0
    const interval = setInterval(() => {
      i++
      setDisplayed(text.slice(0, i))
      if (i >= text.length) {
        clearInterval(interval)
        setDone(true)
      }
    }, speed)
    return () => clearInterval(interval)
  }, [text, speed])

  return { displayed, done }
}

/* ── Typing Message Component ───────────────────────────────────────────── */

export function TypewriterText({ text, onDone }: { text: string; onDone?: () => void }) {
  const { displayed, done } = useTypewriter(text, 16)
  const calledRef = useRef(false)

  useEffect(() => {
    if (done && onDone && !calledRef.current) {
      calledRef.current = true
      onDone()
    }
  }, [done, onDone])

  return (
    <>
      {displayed}
      {!done && <span className="animate-pulse text-primary">▌</span>}
    </>
  )
}

/* ── Fullscreen Image Modal ─────────────────────────────────────────────── */

export function ImageModal({ src, onClose }: { src: string; onClose: () => void }) {
  const handleDownload = async () => {
    try {
      const response = await fetch(src)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `jarvis-image-${Date.now()}.png`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      window.open(src, "_blank")
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm"
      onClick={onClose}
    >
      <div className="relative max-h-[90vh] max-w-[90vw]" onClick={(e) => e.stopPropagation()}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt="Generated image fullscreen"
          className="max-h-[85vh] max-w-[85vw] rounded-lg border border-primary/30 object-contain shadow-2xl"
        />
        <div className="absolute -top-3 right-0 flex gap-2">
          <button
            onClick={handleDownload}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-primary/30 bg-card/90 text-primary shadow-lg backdrop-blur-md transition-colors hover:bg-primary hover:text-primary-foreground"
            aria-label="Download image"
          >
            <Download className="h-4 w-4" />
          </button>
          <button
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-primary/30 bg-card/90 text-primary shadow-lg backdrop-blur-md transition-colors hover:bg-destructive hover:text-white"
            aria-label="Close fullscreen"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

/* ── Copy-to-clipboard button ───────────────────────────────────────────── */

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const ta = document.createElement("textarea")
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand("copy")
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 rounded-md border border-primary/20 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.15em] text-primary transition-colors hover:bg-primary/10"
    >
      {copied ? (
        <>
          <Check className="h-3 w-3" /> Copied
        </>
      ) : (
        <>
          <ClipboardCopy className="h-3 w-3" /> {label}
        </>
      )}
    </button>
  )
}

/* ── Email Draft Card with editable recipient ───────────────────────────── */

export function EmailDraftCard({
  action,
  onSend,
  sending,
}: {
  action: ClientAction
  onSend: (to: string, subject: string, body: string) => void
  sending: boolean
}) {
  const [to, setTo] = useState(action.email_to || "")
  const [subject, setSubject] = useState(action.email_subject || "")
  const [body, setBody] = useState(action.email_body || "")

  const mailtoLink = `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`

  return (
    <div className="mt-3 space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <Mail className="h-3 w-3" />
        Email Draft
      </div>
      <input
        value={to}
        onChange={(e) => setTo(e.target.value)}
        placeholder="Recipient email address"
        className="w-full rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Recipient email address"
      />
      <input
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        placeholder="Subject"
        className="w-full rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Email subject"
      />
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Email body"
        rows={4}
        className="max-h-[160px] w-full resize-y rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] leading-relaxed text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Email body"
      />
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          disabled={sending}
          onClick={() => onSend(to, subject, body)}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          <Mail className="h-3 w-3" /> {sending ? "Sending…" : "Send via Gmail"}
        </button>
        <a
          href={mailtoLink}
          className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-accent-foreground transition-opacity hover:opacity-90"
        >
          <Mail className="h-3 w-3" /> Open in Mail App
        </a>
        <CopyButton text={mailtoLink} label="Copy link" />
        <CopyButton text={`Subject: ${subject}\n\n${body}`} label="Copy email" />
      </div>
    </div>
  )
}

/* ── Inline Image with loading state ────────────────────────────────────── */

export function InlineImage({
  src,
  onFullscreen,
}: {
  src: string
  onFullscreen: () => void
}) {
  const [loaded, setLoaded] = useState(false)
  const [errored, setErrored] = useState(false)

  return (
    <div className="group relative mt-3">
      {!loaded && !errored && (
        <div className="flex h-[200px] items-center justify-center rounded-md border border-primary/20 bg-primary/5">
          <div className="flex flex-col items-center gap-2 text-primary/60">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="font-mono text-[10px] uppercase tracking-[0.2em]">
              Generating image…
            </span>
          </div>
        </div>
      )}
      {errored && (
        <div className="flex h-[120px] items-center justify-center rounded-md border border-destructive/30 bg-destructive/5">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-destructive">
            Image failed to load
          </span>
        </div>
      )}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt="AI generated image"
        className={cn(
          "max-h-[240px] w-full rounded-md border border-primary/20 object-cover transition-opacity",
          loaded ? "opacity-100" : "h-0 opacity-0",
        )}
        loading="eager"
        onLoad={() => setLoaded(true)}
        onError={() => setErrored(true)}
      />
      {loaded && (
        <div className="absolute right-2 top-2 flex gap-1.5 opacity-0 transition-opacity group-hover:opacity-100">
          <button
            onClick={onFullscreen}
            className="flex h-8 w-8 items-center justify-center rounded-md bg-card/80 text-primary shadow backdrop-blur-sm transition-colors hover:bg-primary hover:text-primary-foreground"
            aria-label="View fullscreen"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={async () => {
              try {
                const r = await fetch(src)
                const blob = await r.blob()
                const url = URL.createObjectURL(blob)
                const a = document.createElement("a")
                a.href = url
                a.download = `jarvis-image-${Date.now()}.png`
                document.body.appendChild(a)
                a.click()
                document.body.removeChild(a)
                URL.revokeObjectURL(url)
              } catch {
                window.open(src, "_blank")
              }
            }}
            className="flex h-8 w-8 items-center justify-center rounded-md bg-card/80 text-primary shadow backdrop-blur-sm transition-colors hover:bg-primary hover:text-primary-foreground"
            aria-label="Download image"
          >
            <Download className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  )
}

/* ── Web Search Sources ────────────────────────────────────────────────── */

export interface SearchResult {
  title: string
  url: string
  snippet: string
}

function hostname(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "")
  } catch {
    return url
  }
}

export function SearchSourcesCard({ results }: { results: SearchResult[] }) {
  if (!results.length) return null
  return (
    <div className="mt-3 space-y-1.5 border-t border-primary/15 pt-2">
      <p className="font-mono text-[9px] uppercase tracking-[0.28em] text-muted-foreground/70">
        Sources
      </p>
      {results.map((result, i) => (
        <a
          key={`${result.url}-${i}`}
          href={result.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block truncate text-[11px] text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
        >
          {result.title || hostname(result.url)} — {hostname(result.url)}
        </a>
      ))}
    </div>
  )
}

export function ReadSourceTag({ url }: { url: string | null }) {
  if (!url) return null
  return (
    <div className="mt-3 border-t border-primary/15 pt-2">
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[11px] text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
      >
        Read: {hostname(url)}
      </a>
    </div>
  )
}

/* ── Calendar Event Draft Card (create or edit) ─────────────────────────── */

export function CalendarEventDraftCard({
  action,
  onSave,
  saving,
}: {
  action: ClientAction
  onSave: (
    eventId: string | undefined,
    summary: string,
    start: string,
    end: string,
    description: string,
    location: string,
    attendees: string[],
  ) => void
  saving: boolean
}) {
  const [summary, setSummary] = useState(action.event_summary || "")
  const [start, setStart] = useState(action.event_start || "")
  const [end, setEnd] = useState(action.event_end || "")
  const [description, setDescription] = useState(action.event_description || "")
  const [location, setLocation] = useState(action.event_location || "")
  const [attendeesText, setAttendeesText] = useState((action.event_attendees || []).join(", "))

  const isEdit = Boolean(action.event_id)

  const handleSubmit = () => {
    const attendees = attendeesText
      .split(",")
      .map((email) => email.trim())
      .filter(Boolean)
    onSave(action.event_id, summary, start, end, description, location, attendees)
  }

  return (
    <div className="mt-3 space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <CalendarClock className="h-3 w-3" />
        {isEdit ? "Edit Calendar Event" : "New Calendar Event"}
      </div>
      <input
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        placeholder="Event title"
        className="w-full rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Event title"
      />
      <div className="flex gap-2">
        <input
          type="datetime-local"
          value={start.slice(0, 16)}
          onChange={(e) => setStart(e.target.value)}
          className="w-1/2 rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground focus:outline-none"
          aria-label="Start date and time"
        />
        <input
          type="datetime-local"
          value={end.slice(0, 16)}
          onChange={(e) => setEnd(e.target.value)}
          className="w-1/2 rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground focus:outline-none"
          aria-label="End date and time"
        />
      </div>
      <input
        value={location}
        onChange={(e) => setLocation(e.target.value)}
        placeholder="Location (optional)"
        className="w-full rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Event location"
      />
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description (optional)"
        rows={2}
        className="max-h-[100px] w-full resize-y rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] leading-relaxed text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Event description"
      />
      <input
        value={attendeesText}
        onChange={(e) => setAttendeesText(e.target.value)}
        placeholder="Attendee emails, comma-separated (optional — they'll get a real invite)"
        className="w-full rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Attendee email addresses"
      />
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          disabled={saving}
          onClick={handleSubmit}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          <CalendarClock className="h-3 w-3" />
          {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Event"}
        </button>
      </div>
    </div>
  )
}

/* ── Calendar Event Delete Confirmation ─────────────────────────────────── */

export function CalendarEventDeleteConfirm({
  action,
  onConfirm,
  onCancel,
  deleting,
}: {
  action: ClientAction
  onConfirm: (eventId: string) => void
  onCancel: () => void
  deleting: boolean
}) {
  return (
    <div className="mt-3 space-y-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-destructive">
        <CalendarClock className="h-3 w-3" />
        Delete Event?
      </div>
      <p className="text-[11px] text-foreground">
        {action.event_summary || "This event"}
        {action.event_start ? ` — ${action.event_start}` : ""}
      </p>
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          disabled={deleting}
          onClick={() => action.event_id && onConfirm(action.event_id)}
          className="inline-flex items-center gap-1.5 rounded-md bg-destructive px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-white transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {deleting ? "Deleting…" : "Delete Event"}
        </button>
        <button
          type="button"
          disabled={deleting}
          onClick={onCancel}
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card/50 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

/* ── Business Report Card ──────────────────────────────────────────────── */

export function BusinessReportCard({ action }: { action: ClientAction }) {
  const sections = action.report_sections || []
  const sources = action.report_sources || []
  if (!sections.length) return null

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <FileText className="h-3 w-3" />
        Business Report{action.report_topic ? `: ${action.report_topic}` : ""}
      </div>
      <div className="space-y-2.5">
        {sections.map((section, i) => (
          <div key={`${section.heading}-${i}`}>
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground/80">
              {section.heading}
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-foreground">{section.content}</p>
          </div>
        ))}
      </div>
      {sources.length > 0 && (
        <div className="space-y-1.5 border-t border-accent/15 pt-2">
          <p className="font-mono text-[9px] uppercase tracking-[0.28em] text-muted-foreground/70">
            Sources
          </p>
          {sources.map((url, i) => (
            <a
              key={`${url}-${i}`}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="block truncate text-[11px] text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
            >
              {url}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Content Draft Card ────────────────────────────────────────────────── */

const CONTENT_FORMAT_LABELS: Record<string, string> = {
  social_caption: "Social Caption",
  script: "Script",
  marketing_copy: "Marketing Copy",
}

export function ContentDraftCard({ action }: { action: ClientAction }) {
  const body = action.content_body || ""
  if (!body) return null
  const formatLabel = (action.content_format && CONTENT_FORMAT_LABELS[action.content_format]) || "Content"
  const sources = action.content_sources || []

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
          <FileText className="h-3 w-3" />
          {formatLabel}
          {action.content_platform ? ` · ${action.content_platform}` : ""}
          {action.content_topic ? `: ${action.content_topic}` : ""}
        </div>
        <CopyButton text={body} label="Copy" />
      </div>
      <p className="whitespace-pre-wrap text-[11px] leading-relaxed text-foreground">{body}</p>
      {sources.length > 0 && (
        <div className="space-y-1.5 border-t border-accent/15 pt-2">
          <p className="font-mono text-[9px] uppercase tracking-[0.28em] text-muted-foreground/70">
            Sources
          </p>
          {sources.map((url, i) => (
            <a
              key={`${url}-${i}`}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="block truncate text-[11px] text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
            >
              {url}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Subtitle Result Card ──────────────────────────────────────────────── */

export function SubtitleResultCard({ action }: { action: ClientAction }) {
  const content = action.subtitle_content || ""
  if (!content) return null

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
          <FileText className="h-3 w-3" />
          Subtitles{action.subtitle_file_path ? `: ${action.subtitle_file_path}` : ""}
        </div>
        <CopyButton text={content} label="Copy" />
      </div>
      <pre className="max-h-[240px] overflow-y-auto whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-foreground">
        {content}
      </pre>
    </div>
  )
}

/* ── File Upload Card ──────────────────────────────────────────────────── */

export function FileUploadCard({
  action,
  backendUrl,
  onUploaded,
}: {
  action: ClientAction
  backendUrl: string
  onUploaded: (filePath: string, fileName: string) => void
}) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = (file: File) => {
    setUploading(true)
    setProgress(0)
    setError(null)

    const xhr = new XMLHttpRequest()
    xhr.open("POST", `${backendUrl}/api/uploads`)
    xhr.withCredentials = true
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        setProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
    xhr.onload = () => {
      setUploading(false)
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText)
          setDone(true)
          onUploaded(data.file_path, data.file_name)
        } catch {
          setError("Upload succeeded but the response was invalid.")
        }
      } else {
        setError(`Upload failed (${xhr.status}).`)
      }
    }
    xhr.onerror = () => {
      setUploading(false)
      setError("Upload failed — check your connection to the backend.")
    }

    const formData = new FormData()
    formData.append("file", file)
    xhr.send(formData)
  }

  if (done) {
    return (
      <div className="mt-3 rounded-lg border border-accent/30 bg-accent/5 p-3 text-[11px] text-accent">
        Upload complete — continuing…
      </div>
    )
  }

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault()
        const file = e.dataTransfer.files?.[0]
        if (file) handleFile(file)
      }}
      className="mt-3 space-y-2 rounded-lg border border-dashed border-accent/40 bg-accent/5 p-4 text-center"
    >
      <div className="flex items-center justify-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <UploadCloud className="h-3 w-3" />
        Upload for {action.upload_purpose || "processing"}
      </div>
      {uploading ? (
        <div className="space-y-1">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-accent/15">
            <div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="font-mono text-[10px] text-muted-foreground">Uploading… {progress}%</p>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-accent-foreground transition-opacity hover:opacity-90"
        >
          Choose File
        </button>
      )}
      {error && <p className="text-[10px] text-destructive">{error}</p>}
      <input
        ref={inputRef}
        type="file"
        accept="video/*,audio/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
        }}
      />
    </div>
  )
}

/* ── Silence Removal Result Card ───────────────────────────────────────── */

export function SilenceRemovalResultCard({ action }: { action: ClientAction }) {
  if (!action.silence_output_path) return null

  return (
    <div className="mt-3 space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <FileText className="h-3 w-3" />
        Silence Removed
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-foreground">
        <span className="text-muted-foreground">Original</span>
        <span>{action.silence_original_duration?.toFixed(1)}s</span>
        <span className="text-muted-foreground">New</span>
        <span>{action.silence_new_duration?.toFixed(1)}s</span>
        <span className="text-muted-foreground">Removed</span>
        <span>{action.silence_removed_seconds?.toFixed(1)}s</span>
        <span className="text-muted-foreground">Segments kept</span>
        <span>{action.silence_segment_count}</span>
      </div>
      <p className="truncate font-mono text-[10px] text-muted-foreground">{action.silence_output_path}</p>
    </div>
  )
}

/* ── Highlight Detection Result Card ───────────────────────────────────── */

export function HighlightDetectionResultCard({ action }: { action: ClientAction }) {
  const clips = action.highlight_clips || []
  if (!clips.length) return null

  return (
    <div className="mt-3 space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <FileText className="h-3 w-3" />
        Highlights
      </div>
      <div className="space-y-2.5">
        {clips.map((clip, i) => (
          <div key={`${clip.path}-${i}`}>
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground/80">
              {clip.start.toFixed(1)}s – {clip.end.toFixed(1)}s
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-foreground">{clip.reason}</p>
            <p className="mt-1 truncate font-mono text-[10px] text-muted-foreground">{clip.path}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
