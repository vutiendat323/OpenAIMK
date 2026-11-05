import { VoicePlayer, type VoiceAudio } from './voiceAudio'

interface Fallback {
  push(chunk: VoiceAudio): void
  stop(): void
  interrupt(): void
  resume(): void
  close(): void
}

// Trend's speech over WebRTC: the browser's own playout (adaptive jitter buffer
// and loss concealment) plays it outside this page's JavaScript thread, so the
// Pet's rendering cannot delay it. The kiosk socket only carries PCM while this
// connection is not established; that PCM still plays through the fallback.
export class RtcSpeaker {
  meter: AnalyserNode | null = null
  private peer: RTCPeerConnection
  private element: HTMLAudioElement
  private source: MediaStreamAudioSourceNode | null = null
  private closed = false
  private context: AudioContext
  private fallback: Fallback

  static async create(
    context: AudioContext,
    playback: (playing: boolean) => void,
    output?: AudioNode,
  ) {
    return new RtcSpeaker(context, await VoicePlayer.create(context, playback, output))
  }

  constructor(
    context: AudioContext,
    fallback: Fallback,
    createPeer = () => new RTCPeerConnection({ iceServers: [] }),
    createElement = () => new Audio(),
  ) {
    this.context = context
    this.fallback = fallback
    this.peer = createPeer()
    this.element = createElement()
    this.peer.ontrack = ({ streams }) => {
      const stream = streams[0]
      if (this.closed || !stream) return
      this.element.srcObject = stream
      void this.element.play().catch(() => {})
      this.source?.disconnect()
      this.source = this.context.createMediaStreamSource(stream)
      const meter = this.context.createAnalyser()
      meter.fftSize = 256
      this.source.connect(meter)
      this.meter = meter
    }
  }

  async connect(negotiate: (sdp: string) => Promise<string>) {
    const peer = this.peer
    peer.addTransceiver('audio', { direction: 'recvonly' })
    await peer.setLocalDescription(await peer.createOffer())
    await new Promise<void>((done) => {
      if (peer.iceGatheringState === 'complete') return done()
      const timer = setTimeout(done, 3000)
      peer.onicegatheringstatechange = () => {
        if (peer.iceGatheringState !== 'complete') return
        clearTimeout(timer)
        done()
      }
    })
    if (this.closed || !peer.localDescription) return
    const answer = await negotiate(peer.localDescription.sdp)
    if (this.closed) return
    await peer.setRemoteDescription({ type: 'answer', sdp: answer })
  }

  /** Numbers from the browser's playout of the received speech (NetEQ), for diagnosis. */
  async readStats(report: (stats: Record<string, number>) => void) {
    if (this.closed) return
    const stats = await this.peer.getStats()
    stats.forEach((entry: Record<string, unknown>) => {
      if (entry.type !== 'inbound-rtp' || entry.kind !== 'audio') return
      const numbers: Record<string, number> = {}
      for (const [key, value] of Object.entries(entry))
        if (typeof value === 'number' && key !== 'timestamp' && key !== 'ssrc') numbers[key] = value
      report(numbers)
    })
  }

  /** Retry playback after a user gesture if the browser blocked autoplay. */
  unlock() {
    if (this.element.srcObject && this.element.paused) void this.element.play().catch(() => {})
  }

  push(chunk: VoiceAudio) {
    this.fallback.push(chunk)
  }

  stop() {
    this.fallback.stop()
  }

  interrupt() {
    this.element.muted = true
    this.fallback.interrupt()
  }

  resume() {
    this.element.muted = false
    this.fallback.resume()
  }

  close() {
    this.closed = true
    this.fallback.close()
    this.source?.disconnect()
    this.source = null
    this.meter = null
    this.element.pause()
    this.element.srcObject = null
    this.peer.close()
  }
}
