"use client"

import { useCallback, useRef, useState } from "react"
import { apiHeaders } from "@/lib/api"

const POLL_INTERVAL_MS = 60_000

interface ReminderTask {
  id: number
  title: string
  done: boolean
  due_at: string | null
}

export function useTaskReminders(backendUrl: string) {
  const [remindersEnabled, setRemindersEnabled] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const notifiedRef = useRef<Set<number>>(new Set())

  const checkDueTasks = useCallback(async () => {
    try {
      const res = await fetch(`${backendUrl}/api/tasks?include_done=false`, { headers: apiHeaders() })
      if (!res.ok) return
      const data = await res.json()
      const tasks: ReminderTask[] = data.tasks || []
      const now = Date.now()

      for (const task of tasks) {
        if (!task.due_at || notifiedRef.current.has(task.id)) continue
        const dueTime = new Date(task.due_at).getTime()
        if (Number.isNaN(dueTime) || dueTime > now) continue

        notifiedRef.current.add(task.id)
        if (typeof Notification !== "undefined" && Notification.permission === "granted") {
          new Notification("JARVIS Reminder", { body: task.title })
        }
      }
    } catch {
      // Silent failure — the next poll will just retry
    }
  }, [backendUrl])

  const enableReminders = useCallback(async () => {
    if (typeof Notification === "undefined") return false
    const permission = await Notification.requestPermission()
    if (permission !== "granted") return false

    setRemindersEnabled(true)
    checkDueTasks()
    intervalRef.current = setInterval(checkDueTasks, POLL_INTERVAL_MS)
    return true
  }, [checkDueTasks])

  const disableReminders = useCallback(() => {
    setRemindersEnabled(false)
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  return { remindersEnabled, enableReminders, disableReminders }
}
