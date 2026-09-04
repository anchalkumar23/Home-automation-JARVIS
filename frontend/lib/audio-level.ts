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
