"use client"

import { cn } from "@/lib/utils"

type ReactorState = "idle" | "listening" | "thinking" | "speaking"

const STATE_LABEL: Record<ReactorState, string> = {
  idle: "STANDBY",
  listening: "LISTENING",
  thinking: "PROCESSING",
  speaking: "RESPONDING",
}

export function ArcReactor({
  state = "idle",
  className,
}: {
  state?: ReactorState
  className?: string
}) {
  const active = state !== "idle"

  return (
    <div className={cn("relative aspect-square w-full max-w-[420px]", className)} aria-hidden="true">
      {/* Outer rotating tick ring */}
      <svg viewBox="0 0 200 200" className="absolute inset-0 h-full w-full animate-hud-spin-slow text-primary/40">
        <circle cx="100" cy="100" r="96" fill="none" stroke="currentColor" strokeWidth="0.5" strokeDasharray="1 3" />
      </svg>

      {/* Segmented ring */}
      <svg viewBox="0 0 200 200" className="absolute inset-0 h-full w-full animate-hud-spin-reverse text-primary/60">
        <circle
          cx="100"
          cy="100"
          r="84"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeDasharray="40 14 24 14 60 14"
          strokeLinecap="round"
        />
      </svg>

      {/* Inner spinning dashed ring */}
      <svg
        viewBox="0 0 200 200"
        className={cn("absolute inset-0 h-full w-full text-accent/70", active ? "animate-hud-spin" : "animate-hud-spin-slow")}
      >
        <circle cx="100" cy="100" r="70" fill="none" stroke="currentColor" strokeWidth="0.75" strokeDasharray="2 6" />
      </svg>

      {/* Static crosshair frame */}
      <svg viewBox="0 0 200 200" className="absolute inset-0 h-full w-full text-primary/30">
        <circle cx="100" cy="100" r="58" fill="none" stroke="currentColor" strokeWidth="0.5" />
        <line x1="100" y1="6" x2="100" y2="20" stroke="currentColor" strokeWidth="0.75" />
        <line x1="100" y1="180" x2="100" y2="194" stroke="currentColor" strokeWidth="0.75" />
        <line x1="6" y1="100" x2="20" y2="100" stroke="currentColor" strokeWidth="0.75" />
        <line x1="180" y1="100" x2="194" y2="100" stroke="currentColor" strokeWidth="0.75" />
      </svg>

      {/* Core */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div
          className={cn(
            "relative flex aspect-square w-[44%] items-center justify-center rounded-full animate-core-pulse",
          )}
          style={{
            background:
              "radial-gradient(circle at 50% 50%, color-mix(in oklch, var(--primary) 90%, white) 0%, var(--primary) 28%, color-mix(in oklch, var(--primary) 40%, transparent) 60%, transparent 75%)",
            boxShadow:
              "0 0 50px color-mix(in oklch, var(--primary) 60%, transparent), 0 0 120px color-mix(in oklch, var(--primary) 35%, transparent)",
          }}
        >
          {/* triangular core segments */}
          <svg viewBox="0 0 100 100" className="h-[70%] w-[70%] text-primary-foreground/80">
            <polygon points="50,18 70,56 30,56" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
            <polygon
              points="50,82 30,44 70,44"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinejoin="round"
              opacity="0.6"
            />
            <circle cx="50" cy="50" r="6" fill="currentColor" />
          </svg>
        </div>
      </div>

      {/* Center status label */}
      <div className="pointer-events-none absolute inset-0 flex items-end justify-center pb-[12%]">
        <span className="font-mono text-[10px] tracking-[0.4em] text-primary/80 text-glow">
          {STATE_LABEL[state]}
        </span>
      </div>
    </div>
  )
}
