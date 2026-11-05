import { afterEach, describe, expect, it, vi } from 'vitest'
import { AvatarPlayer, audioPackets } from './avatarPlayer'

describe('avatar PCM streaming', () => {
  it('splits aligned stereo PCM without changing bytes', () => {
    const raw = String.fromCharCode(...Array.from({ length: 15360 }, (_, i) => i % 256))
    const packets = audioPackets({ data: btoa(raw), sampleRate: 48000, numChannels: 2 })
    expect(packets).toHaveLength(1)
    expect(packets.map((p) => atob(p.data)).join('')).toBe(raw)
    const longer = audioPackets({ data: btoa(raw + raw), sampleRate: 48000, numChannels: 2 })
    expect(longer).toHaveLength(2)
    expect(longer.map((p) => atob(p.data)).join('')).toBe(raw + raw)
  })
  it('rejects malformed, empty and unaligned audio', () => {
    for (const data of ['', '%%%', 'AA=='])
      expect(() => audioPackets({ data, sampleRate: 16000, numChannels: 1 })).toThrow()
    expect(() => audioPackets({ data: 'AAA=', sampleRate: 0, numChannels: 1 })).toThrow()
  })
})

describe('avatar transport lifecycle', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('mutes locally before reset and releases transport on close', () => {
    const calls: string[] = []
    class Socket {
      static OPEN = 1
      readyState = 1
      bufferedAmount = 0
      send(raw: string) {
        calls.push(JSON.parse(raw).type)
      }
      close() {
        calls.push('socket-close')
      }
    }
    class Peer {
      close() {
        calls.push('peer-close')
      }
    }
    vi.stubGlobal(
      'MediaStream',
      class {
        addTrack() {}
      },
    )
    vi.stubGlobal('WebSocket', Socket)
    vi.stubGlobal('RTCPeerConnection', Peer)
    vi.stubGlobal('location', { protocol: 'http:', host: 'localhost' })
    vi.stubGlobal(
      'AudioWorkletNode',
      class {
        port = {
          postMessage: (message: { type?: string }) =>
            calls.push(message.type === 'stop' ? 'speaker-stop' : 'speaker-pcm'),
          onmessage: null,
        }
        connect() {}
        disconnect() {
          calls.push('speaker-close')
        }
      },
    )
    const context = { currentTime: 0, baseLatency: 0.01 }
    const player = new AvatarPlayer(
      context as unknown as AudioContext,
      vi.fn(),
      vi.fn(),
      {} as AudioNode,
    )
    player.stop()
    expect(calls.slice(0, 2)).toEqual(['speaker-stop', 'reset'])
    player.interrupt()
    const before = calls.length
    player.push({ data: 'AAA=', sampleRate: 16000, numChannels: 1 })
    expect(calls).toHaveLength(before)
    player.resume()
    player.push({ data: 'AAA=', sampleRate: 16000, numChannels: 1 })
    expect(calls).toContain('audio')
    player.close()
    player.close()
    expect(calls.filter((value) => value === 'socket-close')).toHaveLength(1)
    expect(calls).toContain('peer-close')
  })
  it('uses the existing player when an older API lacks avatar routes', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 404, ok: false }))
    expect(
      await AvatarPlayer.create({} as AudioContext, '', vi.fn(), vi.fn(), {} as AudioNode),
    ).toBeNull()
  })
})
