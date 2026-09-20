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

const TRANSCRIBE_URL = `${process.env.NEXT_PUBLIC_JARVIS_BACKEND ?? "http://localhost:8000"}/api/transcribe`

async function transcribeAudio(blob: Blob, mimeType: string): Promise<string> {
  const extension = mimeType.includes("ogg") ? "ogg" : mimeType.includes("mp4") ? "mp4" : "webm"
  const formData = new FormData()
  formData.append("audio", blob, `recording.${extension}`)

  const response = await fetch(TRANSCRIBE_URL, { method: "POST", credentials: "include", body: formData })

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
