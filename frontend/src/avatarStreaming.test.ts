import { afterEach, expect, it, vi } from 'vitest'
import { AvatarPlayer } from './avatarPlayer'

function fixture() {
  const sent: Record<string, unknown>[] = []
  const speaker: { type?: string; samples?: Float32Array }[] = []
  vi.stubGlobal(
    'AudioWorkletNode',
    class {
      port = {
        postMessage: (message: { type?: string; samples?: Float32Array }) => speaker.push(message),
        onmessage: null,
      }
      connect() {}
      disconnect() {}
    },
  )
  class Socket {
    static OPEN = 1
    static instance: Socket
    readyState = 1
    bufferedAmount = 0
    constructor() {
      Socket.instance = this
    }
    send(raw: string) {
      this.bufferedAmount += raw.length
      sent.push(JSON.parse(raw))
      setTimeout(() => {
        this.bufferedAmount = 0
      }, 5)
    }
    close() {}
  }
  vi.stubGlobal('window', globalThis)
  vi.stubGlobal(
    'MediaStream',
    class {
      addTrack() {}
    },
  )
  vi.stubGlobal('WebSocket', Socket)
  vi.stubGlobal(
    'RTCPeerConnection',
    class {
      close() {}
    },
  )
  vi.stubGlobal('location', { protocol: 'http:', host: 'localhost' })
  const node = () => ({ connect: vi.fn(), disconnect: vi.fn(), fftSize: 256 })
  const gain = {
    ...node(),
    gain: { value: 0, cancelScheduledValues: vi.fn(), setValueAtTime: vi.fn() },
  }
  const context = { createGain: () => gain, createAnalyser: node, currentTime: 0 }
  const player = new AvatarPlayer(
    context as unknown as AudioContext,
    vi.fn(),
    vi.fn(),
    {} as AudioNode,
  )
  return { player, sent, socket: Socket.instance, speaker }
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

it('plays a whole greeting without flooding the socket or the 500ms engine queue', () => {
  vi.useFakeTimers()
  const { player, sent } = fixture()
  try {
    const greeting = { data: btoa('\0'.repeat(48000 * 2 * 3)), sampleRate: 48000, numChannels: 1 }
    expect(() => player.push(greeting)).not.toThrow()
    expect(sent.filter((x) => x.type === 'audio').length).toBeLessThanOrEqual(2)
    vi.advanceTimersByTime(3500)
    expect(sent.filter((x) => x.type === 'audio')).toHaveLength(38)
  } finally {
    player.close()
  }
})

it('interrupt discards unsent greeting packets before the next turn', () => {
  vi.useFakeTimers()
  const { player, sent } = fixture()
  try {
    player.push({ data: btoa('\0'.repeat(48000 * 2)), sampleRate: 48000, numChannels: 1 })
    player.interrupt()
    const count = sent.filter((x) => x.type === 'audio').length
    vi.advanceTimersByTime(2000)
    expect(sent.filter((x) => x.type === 'audio')).toHaveLength(count)
    player.resume()
    player.push({ data: 'AAA=', sampleRate: 16000, numChannels: 1 })
    vi.advanceTimersByTime(100)
    expect(sent.filter((x) => x.type === 'audio')).toHaveLength(count + 1)
  } finally {
    player.close()
  }
})

it('keeps native speaker PCM intact while the avatar socket stalls and reconnects', () => {
  vi.useFakeTimers()
  const { player, socket, speaker } = fixture()
  try {
    socket.bufferedAmount = 20000
    const chunk = { data: btoa('\x00\x20'.repeat(960)), sampleRate: 48000, numChannels: 1 }
    for (let i = 0; i < 200; i++) {
      player.push(chunk)
      vi.advanceTimersByTime(20)
    }
    const samples = speaker.flatMap((message) => Array.from(message.samples ?? []))
    expect(samples).toHaveLength(200 * 960)
    expect(samples.every((sample) => sample === 0.25)).toBe(true)
    expect(speaker.filter((message) => message.type === 'stop')).toHaveLength(0)
    player.interrupt()
    expect(speaker.filter((message) => message.type === 'stop')).toHaveLength(1)
    player.push(chunk)
    expect(speaker.filter((message) => message.samples)).toHaveLength(200)
  } finally {
    player.close()
  }
})
