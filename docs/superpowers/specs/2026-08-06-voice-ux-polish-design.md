# Core AI Assistant Foundation — Increment 1c: Voice UX Polish

## Context

Increment 1b (bilingual voice input via Groq Whisper transcription) is built and mostly working — see `docs/superpowers/plans/2026-08-06-bilingual-voice-input.md`. During hands-on testing, three things came up:

1. **Wake word appears not to trigger.** The wake-word code (`startWakeWordDetection`/`stopWakeWordDetection` in `frontend/lib/use-speech.ts`, browser `SpeechRecognition`-based) was not touched by 1b at all. Root cause is unconfirmed (pre-existing latent bug vs. a microphone-permission issue), but a real code-level bug was found regardless: `recognition.onerror` silently deactivates the wake-word listener (`wakeActiveRef.current = false; setWakeWordActive(false)`) with zero user-visible feedback whenever a real error occurs (e.g. permission denied) — the "Wake" button just reverts to inactive with no explanation.
2. **Manual-only stop is inconvenient.** 1b deliberately chose toggle recording (click to start, click again to stop) over auto-stop-on-silence, to keep the first voice-input increment simple. Having used it, the request is now for real auto-stop after a gap of silence.
3. **No real-time feedback while speaking.** Because Whisper only returns a transcript after the recording stops (it's a batch endpoint, not streaming), there's no way to show live caption text. A live audio-level indicator is wanted instead, so it's visually clear JARVIS is hearing you while you talk.

Two clarifying decisions were made with the user before design: silence-based auto-stop should use real microphone volume monitoring (not a fixed timer), and live feedback should be a volume/level indicator, not literal live captions (avoiding a second, English-only, less-accurate recognizer running in parallel just for cosmetic text).

## Scope

**In scope:**
1. A new shared audio-level-monitoring utility, reused by both the auto-stop and the live-visualizer features.
2. Silence-triggered auto-stop: after ~5 seconds of near-silence (and a minimum ~1.2 second recording length so a brief pause at the very start can't cut it off instantly), recording stops automatically via the same stop path the manual button already uses.
3. The existing `VoiceVisualizer` component reacts to real microphone volume while `state === "listening"`, instead of its current `Math.random()`-driven fake animation for that state. All other states (idle/thinking/speaking) are unchanged.
4. Wake-word errors (e.g. permission denied) now surface as a message in the comms log via the same `handleVoiceError` mechanism built in 1b, instead of silently deactivating with no explanation.
5. Splitting the wake-word code out of `frontend/lib/use-speech.ts` into its own `frontend/lib/use-wake-word.ts`, since the file has grown past a comfortable size and wake-word logic is a well-bounded, mostly-independent concern.

**Out of scope:**
- Diagnosing *why* wake word isn't triggering in the user's specific environment beyond fixing the silent-failure bug — if it's a browser-permission issue, that's resolved by the user granting permission, not by code changes. If the visible error message reveals a different root cause after this fix ships, that becomes its own follow-up.
- Literal live captions/streaming transcription — explicitly rejected during clarification in favor of the volume indicator.
- Any change to the actual transcription accuracy, backend endpoint, or Whisper model — untouched.

## Design

### Shared building block: `frontend/lib/audio-level.ts` (new file)

A small, focused utility wrapping the Web Audio API:
```typescript
export interface LevelMonitor {
  stop: () => void
}

export function startLevelMonitoring(
  stream: MediaStream,
  onLevel: (levels: number[], averageVolume: number) => void,
): LevelMonitor
```
It creates an `AudioContext` + `AnalyserNode` attached to the same `MediaStream` already captured for recording (via `getUserMedia`), and calls `onLevel` on every animation frame with the raw frequency-bin levels (0–255 each) and their average. `stop()` cancels the animation loop and closes the audio context/disconnects the source — called when recording stops, to avoid leaking audio resources. This is the single source of truth both other features read from; there is no second, separate audio-analysis path.

### Silence-triggered auto-stop

Inside `startListening` (`frontend/lib/use-speech.ts`), once `MediaRecorder` starts, `startLevelMonitoring` runs against the same stream. Its `onLevel` callback tracks elapsed silence time using local variables scoped to that recording session (a timestamp reset whenever volume rises above a quiet threshold). Once volume has stayed below the threshold for 5 seconds *and* at least ~1.2 seconds have elapsed since recording started, it calls `recorder.stop()` directly — the exact same object the manual stop path already uses via `recorder.onstop`, so the upload/transcription flow behaves identically regardless of whether the stop was manual or silence-triggered. The manual mic-button/keyboard-shortcut stop path is unchanged and still works for stopping early.

The volume threshold is a tunable constant with no universal "correct" value (depends on microphone sensitivity and room noise) — it starts at a reasonable default and may need adjustment after manual testing.

### Live audio-level visualization

`micLevelsRef` (a plain `useRef<number[]>`, not React state) is updated in-place by the same `onLevel` callback used for silence detection — this avoids triggering ~60 re-renders per second, consistent with `VoiceVisualizer`'s existing pattern of animating via direct DOM mutation inside its own `requestAnimationFrame` loop rather than through React state.

`VoiceVisualizer` gains a new optional prop, `levelsRef?: React.RefObject<number[]>`. Inside its existing animation loop, when `state === "listening"` and `levelsRef.current` has data, bar heights are computed from the real levels (mapped proportionally across the existing 48 bars) instead of the current sine/random formula. If no level data is available yet (e.g. the brief moment before the analyser initializes), it falls back to the existing fake-animation formula — no visual gap or error state. Every other visualizer state is untouched.

### Wake-word error surfacing

`startWakeWordDetection` in the new `frontend/lib/use-wake-word.ts` gains an optional second parameter, `onError?: (message: string) => void`, called from `recognition.onerror` whenever a real error occurs (i.e. not `'no-speech'` or `'aborted'`, the same condition that already exists). `jarvis-interface.tsx` passes its existing `handleVoiceError` callback (built in 1b) here — reusing the same comms-log-message mechanism rather than introducing a new one.

### File structure change: extracting `use-wake-word.ts`

`frontend/lib/use-speech.ts` is already close to 300 lines after 1b; this increment adds audio-level integration on top. The wake-word code is well-bounded — its only interaction with the rest of the app is that `jarvis-interface.tsx` calls the (recording-side) `startListening` from inside the wake-word trigger callback, and that already happens at the component level, not inside the hook internals. It splits cleanly:
- `frontend/lib/use-wake-word.ts` (new): `wakeWordActive`, `wakeWordSupported`, `startWakeWordDetection`, `stopWakeWordDetection`.
- `frontend/lib/use-speech.ts`: keeps voice recording (`startListening`/`stopListening`, now with silence auto-stop and level monitoring), `speak`/`cancelSpeech`, voice loading, and the new `micLevelsRef`.
- `jarvis-interface.tsx` calls both hooks and wires them together exactly as it already wires `useSpeech()`'s pieces together today — this is an additive change to its imports/destructuring, not a restructure of its logic.

### Error handling

- If `AudioContext`/`AnalyserNode` construction fails (unsupported browser, or an autoplay-policy suspension that `resume()` can't clear), the auto-stop and live-visualization features simply don't activate for that session — recording and manual stop still work normally, since they don't depend on the analyser. No error is surfaced for this, since it's a silent capability degradation, not a failure of the feature the user asked for (voice input still works).
- Wake-word errors now surface via `handleVoiceError`, per the design above.

### Testing plan (manual, human-in-the-loop per the project's established workflow)

1. Click the mic, speak a short phrase, then go quiet and wait — recording should stop on its own after about 5 seconds of silence, and the transcribed text should still be sent correctly.
2. Click the mic, speak, and manually click again to stop early (before 5 seconds of silence) — should still work exactly as it does today.
3. While recording, watch the central visualizer — it should visibly react to your actual voice volume (louder when speaking, quieter/flatter when not), not just play a generic animation.
4. If the wake-word permission issue from 1b's testing round is still present, clicking "Wake" and having it fail should now show a clear message in the comms log instead of silently reverting.
5. Confirm wake word still activates and hands off to recording correctly when it *is* working (i.e. this change hasn't regressed the case where wake word succeeds).

## Explicitly deferred to future increments

- Root-causing wake-word reliability beyond the silent-failure fix, if the error message reveals a deeper issue.
- Everything else in `AGENT.md` beyond Section 1.
