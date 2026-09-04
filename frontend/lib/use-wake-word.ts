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
