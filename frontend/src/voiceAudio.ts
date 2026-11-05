export interface VoiceAudio {
  data: string
  sampleRate: number
  numChannels: number
}

export class VoicePlayer {
  private epoch = 0
  private playing = false
  private suspended = false
  private node: AudioWorkletNode
  private playback: (playing: boolean) => void

  static async create(
    context: AudioContext,
    playback: (playing: boolean) => void,
    output?: AudioNode,
  ) {
    await context.audioWorklet.addModule('/voice-playback.js')
    return new VoicePlayer(context, playback, output)
  }

  constructor(context: AudioContext, playback: (playing: boolean) => void, output?: AudioNode) {
    this.playback = playback
    this.node = new AudioWorkletNode(context, 'trend-pcm-playback', {
      numberOfInputs: 0,
      numberOfOutputs: 1,
      outputChannelCount: [1],
      // Native packet gaps reached 123ms and kiosk UI stalls exceeded 100ms.
      // Keep 160ms of PCM before starting; still cap device buffering at 200ms.
      processorOptions: {
        bufferSeconds: Math.min(0.2, Math.max(0.16, 2 * (context.baseLatency || 0) + 0.05)),
      },
    })
    this.node.connect(output || context.destination)
    this.node.port.onmessage = ({ data }) => {
      if (data.epoch !== this.epoch) return
      if (data.type === 'overflow') this.stop()
      else if (data.type === 'playing') this.setPlaying(data.value === true)
    }
  }
  private setPlaying(value: boolean) {
    if (this.playing === value) return
    this.playing = value
    this.playback(value)
  }
  interrupt() {
    this.suspended = true
    this.stop()
  }
  resume() {
    this.suspended = false
  }
  push(chunk: VoiceAudio) {
    if (this.suspended) return
    if (
      ![1, 2].includes(chunk.numChannels) ||
      !Number.isInteger(chunk.sampleRate) ||
      chunk.sampleRate < 8000 ||
      chunk.sampleRate > 96000 ||
      chunk.data.length > 600000
    )
      throw new Error('invalid_voice_audio')
    const raw = atob(chunk.data)
    if (!raw.length || raw.length % (2 * chunk.numChannels)) return
    const frames = raw.length / (2 * chunk.numChannels)
    const bytes = Uint8Array.from(raw, (c) => c.charCodeAt(0))
    const view = new DataView(bytes.buffer)
    const samples = new Float32Array(frames)
    for (let i = 0; i < frames; i++)
      for (let ch = 0; ch < chunk.numChannels; ch++)
        samples[i] +=
          view.getInt16((i * chunk.numChannels + ch) * 2, true) / (32768 * chunk.numChannels)
    this.node.port.postMessage({ epoch: this.epoch, samples, rate: chunk.sampleRate }, [
      samples.buffer,
    ])
  }
  stop() {
    this.node.port.postMessage({ type: 'stop', epoch: ++this.epoch })
    this.setPlaying(false)
  }
  close() {
    this.stop()
    this.node.port.onmessage = null
    this.node.disconnect()
  }
}
