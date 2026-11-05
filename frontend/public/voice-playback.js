/* Continuous PCM playback on the audio thread, independent of UI timers. */
class TrendPlayback extends AudioWorkletProcessor {
  constructor(options) {
    super()
    this.bufferSeconds = Math.min(
      0.2,
      Math.max(0.08, options?.processorOptions?.bufferSeconds || 0.08),
    )
    this.epoch = 0
    this.reset()
    this.port.onmessage = ({ data }) => {
      if (data.type === 'stop') {
        this.epoch = data.epoch
        this.reset()
      } else if (data.epoch === this.epoch && data.samples?.length) {
        const duration = data.samples.length / data.rate
        if (this.seconds + duration > 6) {
          this.reset()
          this.port.postMessage({ type: 'overflow', epoch: this.epoch })
          return
        }
        this.chunks.push(data)
        this.seconds += duration
      }
    }
  }
  reset() {
    this.chunks = []
    this.offset = 0
    this.seconds = 0
    this.waited = 0
    this.playing = false
    this.fade = 0
    this.recoveryFrames = 0
  }
  process(_inputs, outputs) {
    const output = outputs[0][0]
    const recovering = this.recoveryFrames > 0
    this.recoveryFrames = Math.max(0, this.recoveryFrames - output.length)
    if (!this.playing) {
      if (!this.chunks.length) return true
      this.waited += output.length / sampleRate
      // Keep the device-adjusted target; don't confuse late opening packets with a
      // short tail. Only flush undersized tails after a separate deadline.
      // A short mid-turn gap already consumed the initial jitter buffer. Avoid
      // adding a fresh 160-240ms wait after every underrun; refill up to 40ms.
      const target = recovering ? Math.min(this.bufferSeconds, 0.04) : this.bufferSeconds
      const deadline = recovering ? 0.04 : 0.24
      if (this.seconds + 1e-9 < target && this.waited < deadline) return true
      this.playing = true
      this.port.postMessage({ type: 'playing', value: true, epoch: this.epoch })
    }
    const ramp = sampleRate * 0.003
    for (let i = 0; i < output.length; i++) {
      const chunk = this.chunks[0]
      if (!chunk) break
      const index = Math.floor(this.offset)
      const fraction = this.offset - index
      const left = chunk.samples[index]
      const right = chunk.samples[index + 1] ?? this.chunks[1]?.samples[0] ?? left
      this.fade = Math.min(1, this.fade + 1 / ramp)
      // Fade an exhausted buffer to zero instead of a discontinuous cut.
      const gain = Math.min(this.fade, (this.seconds * sampleRate) / ramp, 1)
      output[i] = (left + fraction * (right - left)) * Math.max(0, gain)
      this.offset += chunk.rate / sampleRate
      this.seconds = Math.max(0, this.seconds - 1 / sampleRate)
      if (this.offset >= chunk.samples.length) {
        this.offset -= chunk.samples.length
        this.chunks.shift()
      }
    }
    if (!this.chunks.length) {
      this.reset()
      this.recoveryFrames = sampleRate * 0.5
      this.port.postMessage({ type: 'playing', value: false, epoch: this.epoch })
    }
    return true
  }
}
registerProcessor('trend-pcm-playback', TrendPlayback)
