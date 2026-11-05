/* PCM16 mono 16 kHz, 80 ms packets. Output is silent: no local mic loopback. */
class TrendCapture extends AudioWorkletProcessor {
  constructor() { super(); this.phase = 0; this.sum = 0; this.count = 0; this.packet = new Int16Array(1280); this.index = 0; this.generation = 0; this.port.onmessage = ({data}) => { if (Number.isInteger(data?.generation) && data.generation >= 0) { this.generation = data.generation; this.phase = 0; this.sum = 0; this.count = 0; this.index = 0; this.packet = new Int16Array(1280) } } }
  process(inputs) {
    const channels = inputs[0]
    if (!channels?.length) return true
    for (let i = 0; i < channels[0].length; i++) {
      let sample = 0
      for (const channel of channels) sample += channel[i] / channels.length
      this.sum += sample; this.count++; this.phase += 16000
      if (this.phase >= sampleRate) {
        this.phase -= sampleRate
        this.packet[this.index++] = Math.round(Math.max(-1, Math.min(1, this.sum / this.count)) * 32767)
        this.sum = 0; this.count = 0
        if (this.index === 1280) { this.port.postMessage({generation: this.generation, data: this.packet.buffer}, [this.packet.buffer]); this.packet = new Int16Array(1280); this.index = 0 }
      }
    }
    return true
  }
}
registerProcessor('trend-pcm-capture', TrendCapture)
