import { afterEach, expect, it, vi } from 'vitest'
import { VoicePlayer } from './voiceAudio'

afterEach(() => vi.unstubAllGlobals())
it('stops on barge-in and rejects delayed assistant PCM until a new assistant turn', () => {
  const packets: unknown[] = []
  vi.stubGlobal(
    'AudioWorkletNode',
    class {
      port = { postMessage: (packet: unknown) => packets.push(packet), onmessage: null }
      connect() {}
      disconnect() {}
    },
  )
  const player = new VoicePlayer({ destination: {} } as AudioContext, () => {})
  const audio = { data: btoa('\x01\x00'.repeat(100)), sampleRate: 48000, numChannels: 1 }
  player.push(audio)
  expect(packets).toHaveLength(1)
  player.interrupt()
  const stoppedCount = packets.length
  player.push(audio)
  expect(packets).toHaveLength(stoppedCount)
  player.resume()
  player.push(audio)
  expect(packets).toHaveLength(stoppedCount + 1)
  player.close()
})
