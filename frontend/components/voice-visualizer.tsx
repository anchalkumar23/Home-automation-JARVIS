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
