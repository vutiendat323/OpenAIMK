import { VoicePlayer, type VoiceAudio } from './voiceAudio'

// Keep packets at 80 ms, aligned to complete PCM frames.
export function audioPackets(audio: VoiceAudio): VoiceAudio[] {
  const { sampleRate: rate, numChannels: channels } = audio
  if (!Number.isInteger(rate) || rate < 8000 || rate > 96000 || ![1, 2].includes(channels))
    throw new Error('invalid_avatar_pcm')
  if (audio.data.length > 600000) throw new Error('invalid_avatar_pcm')
  const raw = atob(audio.data)
  if (!raw.length || raw.length % (channels * 2)) throw new Error('invalid_avatar_pcm')
  const size = Math.floor(rate * 0.08) * channels * 2
  const packets: VoiceAudio[] = []
  for (let offset = 0; offset < raw.length; offset += size)
    packets.push({ ...audio, data: btoa(raw.slice(offset, offset + size)) })
  return packets
}

export class AvatarPlayer {
  private socket!: WebSocket
  private peer!: RTCPeerConnection
  private epoch = 0
  private speaker: VoicePlayer
  private closed = false
  private suspended = false
  private queue: VoiceAudio[] = []
  private queuedSeconds = 0
  private pumpTimer: ReturnType<typeof setTimeout> | null = null
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private retryCount = 0
  private recovering = false
  private token = ''
  private actions: string[] = []
  private flowControl = false
  private videoOnly = false
  private awaitingAudio = false
  private nextPacketAt: number | null = null
  private cancelConnect: (() => void) | null = null
  private stalledAt = 0
  private stateChanged: (state: string) => void
  private streamChanged: (stream: MediaStream | null) => void

  static async create(
    context: AudioContext,
    token: string,
    playback: (playing: boolean) => void,
    streamChanged: (stream: MediaStream | null) => void,
    output: AudioNode,
    stateChanged: (state: string) => void = () => {},
  ): Promise<AvatarPlayer | null> {
    const response = await fetch('/api/avatar/status', { signal: AbortSignal.timeout(5000) }).catch(
      () => null,
    )
    if (!response?.ok) return null
    const status = await response.json()
    if (!status.enabled) return null
    await context.audioWorklet.addModule('/voice-playback.js')
    const player = new AvatarPlayer(context, playback, streamChanged, output, stateChanged)
    player.actions = Array.isArray(status.actions) ? status.actions : []
    player.videoOnly = status.video_only === true
    // Voice is usable while the optional visual transport connects or recovers.
    player.recovering = true
    void player
      .connect(token)
      .then(() => {
        player.recovering = false
      })
      .catch(() => {
        if (player.closed) return
        player.recovering = false
        player.recover()
      })
    return player
  }

  constructor(
    context: AudioContext,
    playback: (playing: boolean) => void,
    streamChanged: (stream: MediaStream | null) => void,
    output: AudioNode,
    stateChanged: (state: string) => void = () => {},
  ) {
    this.stateChanged = stateChanged
    this.streamChanged = streamChanged
    this.speaker = new VoicePlayer(context, playback, output)
    this.createTransport()
  }

  private createTransport() {
    this.peer = new RTCPeerConnection({ iceServers: [] })
    this.socket = new WebSocket(
      `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/avatar`,
    )
    const stream = new MediaStream()
    this.peer.ontrack = ({ track }) => {
      // Native PCM plays once through the speaker, independently of the
      // optional visual transport and any unexpected remote audio track.
      if (track.kind !== 'video') return
      stream.addTrack(track)
      this.streamChanged(stream)
    }
    this.socket.onclose = () => {
      this.cancelConnect?.()
      this.recover()
    }
    this.peer.onconnectionstatechange = () => {
      if (['failed', 'disconnected'].includes(this.peer.connectionState)) this.recover()
    }
  }

  private async connect(token: string) {
    this.token = token
    this.stateChanged('connecting')
    const peer = this.peer
    const socket = this.socket
    let timer = 0
    try {
      await new Promise<void>((resolve, reject) => {
        timer = window.setTimeout(() => reject(new Error('avatar_connect_timeout')), 15000)
        this.cancelConnect = () => reject(new Error('avatar_connection_closed'))
        socket.onopen = () => this.send({ type: 'auth', token })
        socket.onerror = () => reject(new Error('avatar_connection_failed'))
        socket.onmessage = async ({ data }) => {
          try {
            const message = JSON.parse(data)
            if (message.type === 'ready') {
              this.flowControl = message.flow_control === true
              // Initial status can precede model warmup. Refresh capabilities on
              // recovery so a cold Ditto start does not keep legacy RTP audio.
              if (!this.videoOnly) {
                const status = await fetch('/api/avatar/status', {
                  signal: AbortSignal.timeout(1000),
                }).catch(() => null)
                if (status?.ok) this.videoOnly = (await status.json()).video_only === true
              }
              if (!this.videoOnly) peer.addTransceiver('audio', { direction: 'recvonly' })
              peer.addTransceiver('video', { direction: 'recvonly' })
              await peer.setLocalDescription(await peer.createOffer())
              await new Promise<void>((done) => {
                if (peer.iceGatheringState === 'complete') return done()
                peer.onicegatheringstatechange = () => {
                  if (peer.iceGatheringState === 'complete') done()
                }
              })
              if (this.closed || this.peer !== peer) return
              this.send({ type: 'offer', sdp: peer.localDescription!.sdp })
            } else if (message.type === 'answer') {
              await peer.setRemoteDescription({ type: 'answer', sdp: message.sdp })
              if (this.closed || this.peer !== peer) return
              this.resetVisual()
              this.stateChanged('ready')
              resolve()
            } else if (message.type === 'audio_ack' && message.epoch === this.epoch) {
              this.awaitingAudio = false
            }
          } catch (error) {
            reject(error)
          }
        }
      })
    } finally {
      clearTimeout(timer)
      this.cancelConnect = null
    }
  }

  private send(message: object) {
    if (
      this.closed ||
      this.socket.readyState !== WebSocket.OPEN ||
      this.socket.bufferedAmount > 96000
    )
      throw new Error('avatar_transport_unavailable')
    this.socket.send(JSON.stringify(message))
  }

  push(audio: VoiceAudio) {
    if (this.suspended || this.closed) return
    this.speaker.push(audio)
    if (this.recovering) return
    const packets = audioPackets(audio)
    const duration = packets.reduce((sum, p) => sum + this.duration(p), 0)
    if (this.queuedSeconds + duration > 12) {
      this.recover()
      return
    }
    this.queue.push(...packets)
    this.queuedSeconds += duration
    if (this.pumpTimer === null) this.pump()
  }

  private duration(packet: VoiceAudio) {
    return atob(packet.data).length / (packet.sampleRate * packet.numChannels * 2)
  }

  private pump() {
    this.pumpTimer = null
    if (this.closed || this.suspended || this.recovering || !this.queue.length) return
    if (this.socket.readyState !== WebSocket.OPEN) {
      this.recover()
      return
    }
    if (this.awaitingAudio || this.socket.bufferedAmount > 16384) {
      if (!this.stalledAt) this.stalledAt = Date.now()
      if (Date.now() - this.stalledAt > 2000) {
        this.recover()
        return
      }
      this.pumpTimer = setTimeout(() => this.pump(), 20)
      return
    }
    this.stalledAt = 0
    const packet = this.queue.shift()!
    const seconds = this.duration(packet)
    this.queuedSeconds = Math.max(0, this.queuedSeconds - seconds)
    try {
      this.awaitingAudio = this.flowControl
      this.send({ type: 'audio', epoch: this.epoch, audio: packet })
      // Keep a media clock: callback overhead must not stretch every 20ms packet.
      // Catch-up is limited to 80ms, with one engine-acknowledged packet in flight.
      const now = Date.now()
      this.nextPacketAt = Math.max(this.nextPacketAt ?? now, now - 80) + seconds * 1000
      this.pumpTimer = setTimeout(() => this.pump(), Math.max(0, this.nextPacketAt - now))
    } catch {
      this.recover()
    }
  }

  private recover() {
    if (this.closed || this.recovering) return
    this.recovering = true
    this.resetVisual()
    this.stateChanged('reconnecting')
    this.releaseTransport()
    this.streamChanged(null)
    if (!this.token) return
    const delay = Math.min(500 * 2 ** this.retryCount++, 5000)
    this.retryTimer = setTimeout(async () => {
      if (this.closed) return
      this.createTransport()
      try {
        await this.connect(this.token)
        if (this.closed) return
        this.recovering = false
        this.retryCount = 0
      } catch {
        this.recovering = false
        this.recover()
      }
    }, delay)
  }

  private releaseTransport() {
    this.cancelConnect?.()
    this.socket.onclose = null
    this.socket.onerror = null
    this.socket.onmessage = null
    this.socket.onopen = null
    this.peer.onconnectionstatechange = null
    this.peer.ontrack = null
    this.socket.close()
    this.peer.close()
  }

  interrupt() {
    this.suspended = true
    this.stop()
  }

  resume() {
    this.suspended = false
  }

  action(action: 'idle' | 'wave' | 'smile') {
    if (!this.actions.includes(action) || this.closed || this.recovering) return false
    this.send({ type: 'action', action })
    return true
  }

  availableActions() {
    return [...this.actions]
  }

  stop() {
    this.speaker.stop()
    this.resetVisual()
  }

  private resetVisual() {
    if (this.pumpTimer !== null) clearTimeout(this.pumpTimer)
    this.pumpTimer = null
    this.queue = []
    this.queuedSeconds = 0
    this.stalledAt = 0
    this.awaitingAudio = false
    this.nextPacketAt = null
    if (!this.closed && this.socket.readyState === WebSocket.OPEN) {
      try {
        this.send({ type: 'reset', epoch: ++this.epoch })
      } catch {
        if (!this.recovering) this.recover()
      }
    }
  }

  close() {
    if (this.closed) return
    this.closed = true
    this.speaker.close()
    this.resetVisual()
    if (this.retryTimer !== null) clearTimeout(this.retryTimer)
    this.releaseTransport()
    this.streamChanged(null)
  }
}
