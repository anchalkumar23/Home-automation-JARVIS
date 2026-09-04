# Core AI Assistant Foundation — Increment 1c Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add silence-triggered auto-stop and a real audio-level-reactive visualizer to voice input, fix the wake-word silent-failure bug, and split wake-word logic out of `use-speech.ts` into its own file.

**Architecture:** A new `frontend/lib/audio-level.ts` wraps the Web Audio API `AnalyserNode` to expose live microphone volume from the same `MediaStream` already used for recording. `use-speech.ts` uses it for both silence-based auto-stop and a `micLevelsRef` (a plain ref, not React state, to avoid 60fps re-renders) that `VoiceVisualizer` reads directly inside its existing animation loop. Wake-word code moves to a new `use-wake-word.ts` and gains an `onError` callback wired to the existing `handleVoiceError` from increment 1b.

**Tech Stack:** Next.js/React, browser Web Audio API (`AudioContext`/`AnalyserNode`), no new dependencies.

**Note on git:** the user is handling all git init/commit/push themselves. No task in this plan runs a git command — each task ends with a test/build verification step instead of a commit step.

**Note on testing:** this project has no frontend test framework, and these features depend on browser-only APIs (`MediaRecorder`, `AudioContext`, `getUserMedia`) that would need heavy mocking to unit test meaningfully. Consistent with increments 1a/1b, verification here is `tsc`/`build` checks plus the manual testing plan in Task 6.

---

### Task 1: `frontend/lib/audio-level.ts` (new file)

**Files:**
- Create: `frontend/lib/audio-level.ts`

- [ ] **Step 1: Create the level-monitoring utility**

Create `frontend/lib/audio-level.ts`:
```typescript
export interface LevelMonitor {
  stop: () => void
}

export function startLevelMonitoring(
  stream: MediaStream,
  onLevel: (levels: number[], averageVolume: number) => void,
): LevelMonitor {
  const AudioContextClass =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
  const audioContext = new AudioContextClass()
  audioContext.resume().catch(() => {})

  const source = audioContext.createMediaStreamSource(stream)
  const analyser = audioContext.createAnalyser()
  analyser.fftSize = 128
  source.connect(analyser)

  const dataArray = new Uint8Array(analyser.frequencyBinCount)
  let rafId = 0

  const tick = () => {
    analyser.getByteFrequencyData(dataArray)
    const levels = Array.from(dataArray)
    const average = levels.reduce((sum, value) => sum + value, 0) / levels.length
    onLevel(levels, average)
    rafId = requestAnimationFrame(tick)
  }
  rafId = requestAnimationFrame(tick)

  return {
    stop: () => {
      cancelAnimationFrame(rafId)
      source.disconnect()
      audioContext.close().catch(() => {})
    },
  }
}
```

- [ ] **Step 2: Verify it type-checks**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: no type errors.

---

### Task 2: `frontend/lib/use-wake-word.ts` (new file — extracted from `use-speech.ts`)

**Files:**
- Create: `frontend/lib/use-wake-word.ts`

- [ ] **Step 1: Create the extracted hook with the `onError` addition**

Create `frontend/lib/use-wake-word.ts`. This is the same wake-word logic currently in `use-speech.ts`, moved to its own file, with one addition: `startWakeWordDetection` now accepts an optional `onError` callback, invoked from `recognition.onerror` instead of silently deactivating with no feedback.
```typescript
"use client"

import { useCallback, useEffect, useRef, useState } from "react"

/* eslint-disable @typescript-eslint/no-explicit-any */

export function useWakeWord() {
  const [wakeWordSupported, setWakeWordSupported] = useState(false)
  const [wakeWordActive, setWakeWordActive] = useState(false)

  const wakeRecognitionRef = useRef<any>(null)
  const onWakeRef = useRef<() => void>(() => {})
  const onErrorRef = useRef<(message: string) => void>(() => {})
  // Use a ref to track wake-word-active so the onend closure always sees current value
  const wakeActiveRef = useRef(false)

  useEffect(() => {
    if (typeof window === "undefined") return
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    setWakeWordSupported(Boolean(SpeechRecognition))
  }, [])

  // --- Wake word detection ("Jarvis") ---
  // Uses wakeActiveRef (not state) to avoid stale closure in onend
  const startWakeWordDetection = useCallback(
    (onWake: () => void, onError?: (message: string) => void) => {
      if (typeof window === "undefined") return
      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      if (!SpeechRecognition) return

      try {
        wakeRecognitionRef.current?.stop()
      } catch {
        /* noop */
      }

      const recognition = new SpeechRecognition()
      recognition.continuous = true
      recognition.interimResults = true
      recognition.lang = "en-US"
      onWakeRef.current = onWake
      onErrorRef.current = onError ?? (() => {})

      recognition.onresult = (event: any) => {
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript.toLowerCase()
          if (/\bjarvis\b/i.test(transcript)) {
            onWakeRef.current()
            break
          }
        }
      }
      recognition.onend = () => {
        // Use the REF not the state — state is stale inside this closure
        if (wakeActiveRef.current) {
          try {
            setTimeout(() => {
              if (wakeActiveRef.current) recognition.start()
            }, 300)
          } catch {
            /* ignore */
          }
        }
      }
      recognition.onerror = (e: any) => {
        if (e.error !== "no-speech" && e.error !== "aborted") {
          wakeActiveRef.current = false
          setWakeWordActive(false)
          onErrorRef.current(
            "Wake word detection stopped: microphone access was denied or unavailable.",
          )
        }
      }

      try {
        recognition.start()
        wakeRecognitionRef.current = recognition
        wakeActiveRef.current = true
        setWakeWordActive(true)
      } catch {
        /* cannot start */
      }
    },
    [],
  )

  const stopWakeWordDetection = useCallback(() => {
    wakeActiveRef.current = false
    setWakeWordActive(false)
    try {
      wakeRecognitionRef.current?.stop()
    } catch {
      /* noop */
    }
    wakeRecognitionRef.current = null
  }, [])

  return {
    wakeWordSupported,
    wakeWordActive,
    startWakeWordDetection,
    stopWakeWordDetection,
  }
}
```

- [ ] **Step 2: Verify it type-checks**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: no type errors. (`use-speech.ts` still has its own copy of this code at this point — that's fine, it gets removed in Task 3. Both copies existing briefly is not an error, just temporary duplication mid-refactor.)

---

### Task 3: Rewrite `frontend/lib/use-speech.ts` — remove wake-word, add silence auto-stop + level monitoring

**Files:**
- Modify: `frontend/lib/use-speech.ts` (full-file replacement)

- [ ] **Step 1: Replace the full contents of `use-speech.ts`**

This removes the wake-word code (now in `use-wake-word.ts` from Task 2) and adds silence-triggered auto-stop plus `micLevelsRef` for the live visualizer, built on the `audio-level.ts` module from Task 1.

Replace the full contents of `frontend/lib/use-speech.ts` with:
```typescript
"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { startLevelMonitoring, type LevelMonitor } from "@/lib/audio-level"

export interface VoiceOption {
  name: string
  lang: string
  voiceURI: string
}

/**
 * Scores a SpeechSynthesisVoice for JARVIS-like quality.
 * Higher score = better match.
 */
function scoreVoice(v: SpeechSynthesisVoice): number {
  const name = v.name.toLowerCase()
  let s = 0
  if (/^en[-_]/i.test(v.lang)) s += 10
  if (/male|daniel|david|james|mark|guy|google uk english male/i.test(name)) s += 20
  if (/natural|enhanced|online|premium/i.test(name)) s += 5
  if (!v.localService) s += 1
  return s
}

const TRANSCRIBE_URL = `${process.env.NEXT_PUBLIC_JARVIS_BACKEND ?? "http://127.0.0.1:8000"}/api/transcribe`

async function transcribeAudio(blob: Blob, mimeType: string): Promise<string> {
  const extension = mimeType.includes("ogg") ? "ogg" : mimeType.includes("mp4") ? "mp4" : "webm"
  const formData = new FormData()
  formData.append("audio", blob, `recording.${extension}`)

  const response = await fetch(TRANSCRIBE_URL, { method: "POST", body: formData })

  if (!response.ok) {
    let detail = "Transcription failed."
    try {
      const data = await response.json()
      if (typeof data.detail === "string") detail = data.detail
    } catch {
      // ignore parse failure, use default message
    }
    throw new Error(detail)
  }

  const data = await response.json()
  return typeof data.text === "string" ? data.text : ""
}

const SILENCE_VOLUME_THRESHOLD = 8
const SILENCE_DURATION_MS = 5000
const MIN_RECORDING_MS = 1200

export function useSpeech() {
  const [supported, setSupported] = useState(false)
  const [listening, setListening] = useState(false)
  const [voices, setVoices] = useState<VoiceOption[]>([])
  const [selectedVoiceURI, setSelectedVoiceURI] = useState<string>("")
  const [muted, setMuted] = useState(false)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const micStreamRef = useRef<MediaStream | null>(null)
  const levelMonitorRef = useRef<LevelMonitor | null>(null)
  const micLevelsRef = useRef<number[]>([])
  const onResultRef = useRef<(text: string) => void>(() => {})
  const onErrorRef = useRef<(message: string) => void>(() => {})
  const rawVoicesRef = useRef<SpeechSynthesisVoice[]>([])

  // --- Load voices from speechSynthesis ---
  const loadVoices = useCallback(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return
    const raw = window.speechSynthesis.getVoices()
    if (!raw.length) return
    rawVoicesRef.current = raw

    const english = raw.filter((v) => /^en[-_]/i.test(v.lang))
    const pool = english.length ? english : raw
    const sorted = [...pool].sort((a, b) => scoreVoice(b) - scoreVoice(a))

    const options: VoiceOption[] = sorted.map((v) => ({
      name: v.name,
      lang: v.lang,
      voiceURI: v.voiceURI,
    }))
    setVoices(options)

    setSelectedVoiceURI((prev) => {
      if (prev && sorted.find((v) => v.voiceURI === prev)) return prev
      return sorted[0]?.voiceURI ?? ""
    })
  }, [])

  // --- Initialise capability detection + voice loading ---
  useEffect(() => {
    if (typeof window === "undefined") return

    const hasSynth = "speechSynthesis" in window
    const hasRecorder =
      typeof MediaRecorder !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia)

    setSupported(hasRecorder && hasSynth)

    if (hasSynth) {
      loadVoices()
      window.speechSynthesis.addEventListener("voiceschanged", loadVoices)
      return () => {
        window.speechSynthesis.removeEventListener("voiceschanged", loadVoices)
      }
    }
  }, [loadVoices])

  // --- Primary microphone recording + Whisper transcription ---
  const startListening = useCallback(
    (onResult: (text: string) => void, onError?: (message: string) => void) => {
      onResultRef.current = onResult
      onErrorRef.current = onError ?? (() => {})

      navigator.mediaDevices
        .getUserMedia({ audio: true })
        .then((stream) => {
          micStreamRef.current = stream
          const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : ""
          const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
          audioChunksRef.current = []

          recorder.ondataavailable = (event: BlobEvent) => {
            if (event.data.size > 0) audioChunksRef.current.push(event.data)
          }

          recorder.onstop = async () => {
            levelMonitorRef.current?.stop()
            levelMonitorRef.current = null
            micLevelsRef.current = []
            micStreamRef.current?.getTracks().forEach((track) => track.stop())
            micStreamRef.current = null
            setListening(false)

            const recordedType = recorder.mimeType || "audio/webm"
            const blob = new Blob(audioChunksRef.current, { type: recordedType })
            audioChunksRef.current = []

            if (blob.size === 0) {
              onErrorRef.current("No audio was recorded. Please try again.")
              return
            }

            try {
              const text = await transcribeAudio(blob, recordedType)
              if (!text.trim()) {
                onErrorRef.current("Couldn't make out what you said. Please try again or type your message.")
                return
              }
              onResultRef.current(text)
            } catch (err) {
              onErrorRef.current(
                err instanceof Error
                  ? err.message
                  : "Couldn't transcribe that. Please try again or type your message.",
              )
            }
          }

          const recordingStartedAt = Date.now()
          let silenceStartedAt: number | null = null

          try {
            levelMonitorRef.current = startLevelMonitoring(stream, (levels, average) => {
              micLevelsRef.current = levels

              const now = Date.now()
              if (average < SILENCE_VOLUME_THRESHOLD) {
                if (silenceStartedAt === null) silenceStartedAt = now
                const recordedFor = now - recordingStartedAt
                const silentFor = now - silenceStartedAt
                if (
                  recordedFor >= MIN_RECORDING_MS &&
                  silentFor >= SILENCE_DURATION_MS &&
                  recorder.state !== "inactive"
                ) {
                  recorder.stop()
                }
              } else {
                silenceStartedAt = null
              }
            })
          } catch {
            // Web Audio API unavailable — recording still works, just without
            // auto-stop or a real live visualizer for this session.
            levelMonitorRef.current = null
          }

          mediaRecorderRef.current = recorder
          recorder.start()
          setListening(true)
        })
        .catch(() => {
          onErrorRef.current(
            "Microphone access was denied or unavailable. Please allow microphone access, or type your message instead.",
          )
        })
    },
    [],
  )

  const stopListening = useCallback(() => {
    mediaRecorderRef.current?.stop()
    mediaRecorderRef.current = null
  }, [])

  // --- Speak text using selected voice ---
  const speak = useCallback(
    (text: string, onEnd?: () => void, language?: string) => {
      if (typeof window === "undefined" || !("speechSynthesis" in window) || muted) {
        onEnd?.()
        return
      }
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.rate = 1.02
      utterance.pitch = 0.85

      let selected = rawVoicesRef.current.find((v) => v.voiceURI === selectedVoiceURI)
      if (language === "es") {
        const spanishVoice = rawVoicesRef.current.find((v) => v.lang.toLowerCase().startsWith("es"))
        if (spanishVoice) selected = spanishVoice
      }
      if (selected) {
        utterance.voice = selected
      }
      utterance.onend = () => onEnd?.()
      window.speechSynthesis.speak(utterance)
    },
    [selectedVoiceURI, muted],
  )

  const cancelSpeech = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel()
    }
  }, [])

  return {
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
  }
}
```

- [ ] **Step 2: Verify it type-checks**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: type errors will appear in `frontend/components/jarvis-interface.tsx` at this point (it still imports `wakeWordActive`/`startWakeWordDetection`/etc. from `useSpeech()`, which no longer exports them) — that's expected and gets fixed in Task 5. Confirm the errors are specifically in `jarvis-interface.tsx` and not in `use-speech.ts` itself.

---

### Task 4: `frontend/components/voice-visualizer.tsx` — real audio-level reactivity

**Files:**
- Modify: `frontend/components/voice-visualizer.tsx` (full-file replacement — the file is only 65 lines)

- [ ] **Step 1: Replace the full contents**

Replace the full contents of `frontend/components/voice-visualizer.tsx` with:
```typescript
"use client"

import { useEffect, useRef } from "react"
import type { RefObject } from "react"

type VisualizerState = "idle" | "listening" | "thinking" | "speaking"

const BAR_COUNT = 48

export function VoiceVisualizer({
  state,
  levelsRef,
}: {
  state: VisualizerState
  levelsRef?: RefObject<number[]>
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const barsRef = useRef<HTMLSpanElement[]>([])
  const rafRef = useRef<number>(0)

  useEffect(() => {
    let t = 0
    const animate = () => {
      t += 0.08
      const bars = barsRef.current
      const levels = levelsRef?.current
      for (let i = 0; i < bars.length; i++) {
        const bar = bars[i]
        if (!bar) continue
        let h: number
        const center = Math.abs(i - BAR_COUNT / 2) / (BAR_COUNT / 2) // 0 center -> 1 edges
        const envelope = 1 - center * 0.65

        if (state === "idle") {
          h = 6 + (Math.sin(t * 0.5 + i * 0.4) + 1) * 4
        } else if (state === "listening") {
          if (levels && levels.length > 0) {
            const levelIndex = Math.floor((i / BAR_COUNT) * levels.length)
            const raw = levels[levelIndex] ?? 0
            h = 6 + (raw / 255) * 52 * envelope
          } else {
            h = 8 + (Math.sin(t + i * 0.5) + 1) * 22 * envelope + Math.random() * 14 * envelope
          }
        } else if (state === "thinking") {
          h = 10 + (Math.sin(t * 2 + i * 0.8) + 1) * 10 * envelope
        } else {
          // speaking
          h = 10 + (Math.sin(t * 1.6 + i * 0.35) + 1) * 26 * envelope + Math.random() * 8 * envelope
        }
        bar.style.height = `${Math.max(4, h)}px`
      }
      rafRef.current = requestAnimationFrame(animate)
    }
    rafRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(rafRef.current)
  }, [state, levelsRef])

  const color = state === "speaking" ? "bg-accent" : "bg-primary"

  return (
    <div
      ref={containerRef}
      className="flex h-16 items-center justify-center gap-[3px]"
      role="img"
      aria-label={`Audio visualizer — ${state}`}
    >
      {Array.from({ length: BAR_COUNT }).map((_, i) => (
        <span
          key={i}
          ref={(el) => {
            if (el) barsRef.current[i] = el
          }}
          className={`w-[3px] rounded-full transition-colors duration-300 ${color}`}
          style={{ height: 6, opacity: 0.5 + (1 - Math.abs(i - BAR_COUNT / 2) / (BAR_COUNT / 2)) * 0.5 }}
        />
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Verify it type-checks**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: same `jarvis-interface.tsx` errors as Task 3 (not yet fixed), nothing new from this file.

---

### Task 5: Wire both hooks together in `frontend/components/jarvis-interface.tsx`

**Files:**
- Modify: `frontend/components/jarvis-interface.tsx:23` (add import)
- Modify: `frontend/components/jarvis-interface.tsx:374-390` (split the hook destructure)
- Modify: `frontend/components/jarvis-interface.tsx:557-581` (`toggleWakeWord` — pass `handleVoiceError`)
- Modify: `frontend/components/jarvis-interface.tsx:758` (`VoiceVisualizer` — pass `levelsRef`)

- [ ] **Step 1: Import the new hook**

Modify `frontend/components/jarvis-interface.tsx`, changing line 23 from:
```typescript
import { useSpeech } from "@/lib/use-speech"
```
to:
```typescript
import { useSpeech } from "@/lib/use-speech"
import { useWakeWord } from "@/lib/use-wake-word"
```

- [ ] **Step 2: Split the hook destructure**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `useSpeech()` destructure (current lines 374-390):
```typescript
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
```

- [ ] **Step 3: Pass `handleVoiceError` into the wake-word trigger**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `toggleWakeWord` callback (current lines 557-581):
```typescript
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
```
(The only change from the current version is the added `, handleVoiceError` as the second argument to the outer `startWakeWordDetection(...)` call — the dependency array already includes `handleVoiceError`.)

- [ ] **Step 4: Pass `micLevelsRef` to the visualizer**

Modify `frontend/components/jarvis-interface.tsx`, changing line 758 from:
```typescript
              <VoiceVisualizer state={orbState} />
```
to:
```typescript
              <VoiceVisualizer state={orbState} levelsRef={micLevelsRef} />
```

- [ ] **Step 5: Verify the frontend type-checks and builds**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
npm run build
```
Expected: no type errors; production build completes successfully.

---

### Task 6: End-to-end manual verification

**Files:**
- None (verification only).

- [ ] **Step 1: Restart the frontend (and backend, if not already running)**

Run (PowerShell), in separate terminals as needed:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"; npm run dev
```
Open `http://localhost:3000` in a Chromium-based browser.

- [ ] **Step 2: Verify silence-triggered auto-stop**

Click the mic, speak a short phrase, then go quiet and wait. Expected: recording stops on its own after about 5 seconds of silence, and the transcribed text is still sent and answered correctly.

- [ ] **Step 3: Verify manual stop still works**

Click the mic, speak, and click again to stop before 5 seconds of silence has passed. Expected: works exactly as before — stops immediately, transcribes, sends.

- [ ] **Step 4: Verify the live visualizer reacts to real voice**

While recording, watch the central bar visualizer. Expected: it visibly reacts to actual voice volume — louder/more active when speaking, flatter when quiet — rather than a generic animation unrelated to what's being said.

- [ ] **Step 5: Verify wake-word error surfacing**

Click "Wake." If it fails to activate or later fails, expected: a clear message now appears in the comms log (not a silent revert to inactive with no explanation). If wake word activates and successfully detects "Jarvis," confirm it still correctly hands off into recording as before.

- [ ] **Step 6: Stop both servers**

Ctrl+C in both terminals.

---

## Post-plan: what's explicitly not in this increment

- Root-causing wake-word reliability beyond the silent-failure fix, if the new error message reveals a deeper issue (e.g. a real permission problem) — that becomes its own follow-up if needed.
- Everything else in `AGENT.md` beyond Section 1.
