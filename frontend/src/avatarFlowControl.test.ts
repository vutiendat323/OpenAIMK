import { afterEach, expect, it, vi } from 'vitest'
import { AvatarPlayer } from './avatarPlayer'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

async function fixture(ackDelay = 400, videoOnly: boolean | (() => boolean) = true) {
  vi.useFakeTimers()
  const audio: object[] = []
  const transceivers: { kind: string; direction: string }[] = []
  class Socket {
    static OPEN = 1
    readyState = 0
    bufferedAmount = 0
    onopen: (() => void) | null = null
    onmessage: ((event: { data: string }) => void) | null = null
    constructor() {
      setTimeout(() => {
        this.readyState = 1
        this.onopen?.()
      }, 0)
    }
    send(raw: string) {
      const message = JSON.parse(raw)
      const reply = (data: object, delay = 1) =>
        setTimeout(() => this.onmessage?.({ data: JSON.stringify(data) }), delay)
      if (message.type === 'auth') reply({ type: 'ready', flow_control: true })
      if (message.type === 'offer') reply({ type: 'answer', sdp: 'answer' })
      if (message.type === 'audio') {
        audio.push(message)
        reply({ type: 'audio_ack', epoch: message.epoch }, ackDelay)
      }
    }
    close() {}
  }
  class Peer {
    iceGatheringState = 'complete'
    localDescription = { sdp: 'offer' }
    addTransceiver(kind: string, options: { direction: string }) {
      transceivers.push({ kind, direction: options.direction })
    }
    async createOffer() {
      return this.localDescription
    }
    async setLocalDescription() {}
    async setRemoteDescription() {}
    close() {}
  }
  vi.stubGlobal('window', globalThis)
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        enabled: true,
        video_only: typeof videoOnly === 'function' ? videoOnly() : videoOnly,
      }),
    }),
  )
  vi.stubGlobal('WebSocket', Socket)
  vi.stubGlobal('RTCPeerConnection', Peer)
  vi.stubGlobal(
    'MediaStream',
    class {
      addTrack() {}
    },
  )
  vi.stubGlobal('location', { protocol: 'http:', host: 'localhost' })
  const speaker = {
    postMessage: vi.fn(),
    onmessage: null as null | ((event: { data: object }) => void),
  }
  vi.stubGlobal(
    'AudioWorkletNode',
    class {
      port = speaker
      connect() {}
      disconnect() {}
    },
  )
  const context = { audioWorklet: { addModule: async () => {} }, currentTime: 0, baseLatency: 0.01 }
  const playback = vi.fn()
  const pending = AvatarPlayer.create(
    context as unknown as AudioContext,
    'fixture',
    playback,
    vi.fn(),
    {} as AudioNode,
  )
  await vi.advanceTimersByTimeAsync(20)
  const player = (await pending)!
  playback.mockClear()
  return { player, audio, playback, speaker, transceivers }
}

it('requests only avatar video while native speaker PCM remains independent', async () => {
  const { player, audio, speaker, transceivers } = await fixture()
  try {
    expect(transceivers).toEqual([{ kind: 'video', direction: 'recvonly' }])
    player.push({ data: btoa('\x00\x20'.repeat(960)), sampleRate: 48000, numChannels: 1 })
    expect(audio).toHaveLength(1)
    const pcm = speaker.postMessage.mock.calls.find((call) => call[0].samples)?.[0].samples
    expect(Array.from(pcm as Float32Array)).toEqual(Array(960).fill(0.25))
  } finally {
    player.close()
  }
})

it('keeps audio negotiation for engines without video-only support', async () => {
  const { player, transceivers } = await fixture(400, false)
  try {
    expect(transceivers).toEqual([
      { kind: 'audio', direction: 'recvonly' },
      { kind: 'video', direction: 'recvonly' },
    ])
  } finally {
    player.close()
  }
})

it('refreshes media capabilities when a cold engine becomes ready', async () => {
  let reads = 0
  const { player, transceivers } = await fixture(400, () => ++reads > 1)
  try {
    expect(transceivers).toEqual([{ kind: 'video', direction: 'recvonly' }])
  } finally {
    player.close()
  }
})

it('waits for engine acknowledgment when a cold renderer falls behind', async () => {
  const { player, audio } = await fixture()
  try {
    player.push({ data: btoa('\0'.repeat(48000 * 2)), sampleRate: 48000, numChannels: 1 })
    await vi.advanceTimersByTimeAsync(300)
    expect(audio).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(150)
    expect(audio).toHaveLength(2)
    player.interrupt()
    await vi.advanceTimersByTimeAsync(600)
    expect(audio).toHaveLength(2)
  } finally {
    player.close()
  }
})

it('takes speaking state only from native playback while the renderer loses acknowledgments', async () => {
  const { player, playback, speaker } = await fixture(10000)
  try {
    player.push({ data: btoa('\0'.repeat(48000 * 2)), sampleRate: 48000, numChannels: 1 })
    speaker.onmessage?.({ data: { type: 'playing', epoch: 0, value: true } })
    await vi.advanceTimersByTimeAsync(4000)
    expect(playback.mock.calls.map((call) => call[0])).toEqual([true])
    expect(speaker.postMessage.mock.calls.filter((call) => call[0].type === 'stop')).toHaveLength(0)
    speaker.onmessage?.({ data: { type: 'playing', epoch: 0, value: false } })
    expect(playback.mock.calls.map((call) => call[0])).toEqual([true, false])
  } finally {
    player.close()
  }
})
