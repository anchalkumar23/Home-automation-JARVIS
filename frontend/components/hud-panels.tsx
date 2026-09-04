"use client"

import { useEffect, useState } from "react"
import { Activity, Cpu, Gauge, Radio, ShieldCheck, Wifi } from "lucide-react"

function useTicker(interval = 1500) {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), interval)
    return () => clearInterval(id)
  }, [interval])
  return tick
}

function PanelFrame({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="relative rounded-lg border border-border bg-card/40 p-3 backdrop-blur-sm">
      <div className="absolute -top-px left-3 h-px w-8 bg-primary" />
      <div className="absolute -left-px top-3 h-8 w-px bg-primary" />
      <h3 className="mb-2.5 font-mono text-[10px] tracking-[0.3em] text-muted-foreground">{title}</h3>
      {children}
    </div>
  )
}

function Meter({ label, value, icon: Icon }: { label: string; value: number; icon: React.ElementType }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between font-mono text-[11px]">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <Icon className="size-3 text-primary" aria-hidden="true" />
          {label}
        </span>
        <span className="text-primary text-glow">{Math.round(value)}%</span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-secondary">
        <div
          className="h-full rounded-full bg-primary transition-all duration-700 ease-out"
          style={{ width: `${value}%`, boxShadow: "0 0 8px var(--primary)" }}
        />
      </div>
    </div>
  )
}

export function SystemPanel() {
  const tick = useTicker(1800)
  const cpu = 32 + ((tick * 7) % 40)
  const mem = 48 + ((tick * 5) % 30)
  const net = 60 + ((tick * 11) % 35)

  return (
    <PanelFrame title="SYSTEM DIAGNOSTICS">
      <div className="space-y-2.5">
        <Meter label="CORE LOAD" value={cpu} icon={Cpu} />
        <Meter label="MEMORY" value={mem} icon={Activity} />
        <Meter label="UPLINK" value={net} icon={Wifi} />
      </div>
    </PanelFrame>
  )
}

export function StatusPanel() {
  const items = [
    { label: "ARC REACTOR", value: "STABLE", icon: Gauge },
    { label: "ENCRYPTION", value: "AES-512", icon: ShieldCheck },
    { label: "FREQUENCY", value: "144.0 MHz", icon: Radio },
  ]
  return (
    <PanelFrame title="STATUS ARRAY">
      <ul className="space-y-2 font-mono text-[11px]">
        {items.map((item) => (
          <li key={item.label} className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <item.icon className="size-3 text-accent" aria-hidden="true" />
              {item.label}
            </span>
            <span className="text-accent text-glow-accent">{item.value}</span>
          </li>
        ))}
      </ul>
    </PanelFrame>
  )
}

export function ClockPanel() {
  const [now, setNow] = useState<Date | null>(null)
  useEffect(() => {
    setNow(new Date())
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <PanelFrame title="CHRONOMETER">
      <div className="font-mono">
        <p className="text-2xl tabular-nums tracking-wider text-primary text-glow sm:text-3xl">
          {now ? now.toLocaleTimeString("en-US", { hour12: false }) : "--:--:--"}
        </p>
        <p className="mt-1 text-[10px] tracking-[0.2em] text-muted-foreground sm:text-[11px]">
          {now
            ? now
                .toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "short", day: "numeric" })
                .toUpperCase()
            : "INITIALIZING"}
        </p>
      </div>
    </PanelFrame>
  )
}

