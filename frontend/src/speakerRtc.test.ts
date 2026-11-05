import { expect, it } from 'vitest'
import { RtcSpeaker } from './speakerRtc'
import type { VoiceAudio } from './voiceAudio'

class FakeFallback {
  calls: string[] = []
  push(chunk: VoiceAudio) {
    this.calls.push(`push:${chunk.data}`)
  }
  stop() {
    this.calls.push('stop')
  }
  interrupt() {
    this.calls.push('interrupt')
  }
  resume() {
    this.calls.push('resume')
  }
  close() {
    this.calls.push('close')
  }
}

class FakePeer {
  iceGatheringState = 'complete'
  onicegatheringstatechange: (() => void) | null = null
  ontrack: ((event: { streams: MediaStream[] }) => void) | null = null
  localDescription: { sdp: string } | null = null
  remote: { type: string; sdp: string } | null = null
  transceivers: string[] = []
  closed = false
  addTransceiver(kind: string, init: { direction: string }) {
    this.transceivers.push(`${kind}:${init.direction}`)
  }
  async createOffer() {
    return { type: 'offer', sdp: 'browser-offer' }
  }
  async setLocalDescription(description: { sdp: string }) {
    this.localDescription = description
  }
  async setRemoteDescription(description: { type: string; sdp: string }) {
    this.remote = description
  }
  close() {
    this.closed = true
  }
}

function speaker() {
  const fallback = new FakeFallback()
  const peer = new FakePeer()
  const element = {
    muted: false,
    srcObject: null as MediaStream | null,
    played: 0,
    play() {
      this.played++
      return Promise.resolve()
    },
    pause() {},
  }
  const context = {
    createMediaStreamSource: () => ({ connect() {}, disconnect() {} }),
    createAnalyser: () => ({ fftSize: 0 }),
  } as unknown as AudioContext
  const rtc = new RtcSpeaker(
    context,
    fallback,
    () => peer as unknown as RTCPeerConnection,
    () => element as unknown as HTMLAudioElement,
  )
  return { rtc, fallback, peer, element }
}

it('negotiates a receive-only audio connection through the kiosk socket', async () => {
  const { rtc, peer } = speaker()
  const offers: string[] = []
  await rtc.connect(async (sdp) => {
    offers.push(sdp)
    return 'server-answer'
  })
  expect(peer.transceivers).toEqual(['audio:recvonly'])
  expect(offers).toEqual(['browser-offer'])
  expect(peer.remote).toEqual({ type: 'answer', sdp: 'server-answer' })
})

it('plays the received speech through a media element and exposes its level', async () => {
  const { rtc, peer, element } = speaker()
  await rtc.connect(async () => 'server-answer')
  const stream = {} as MediaStream
  peer.ontrack?.({ streams: [stream] })
  expect(element.srcObject).toBe(stream)
  expect(element.played).toBe(1)
  expect(rtc.meter).not.toBeNull()
})

it('keeps socket PCM playable while WebRTC is unavailable', () => {
  const { rtc, fallback } = speaker()
  rtc.push({ data: 'AAA=', sampleRate: 48000, numChannels: 1 })
  expect(fallback.calls).toEqual(['push:AAA='])
})

it('silences speech on interruption until Trend speaks again', async () => {
  const { rtc, fallback, element } = speaker()
  rtc.interrupt()
  expect(element.muted).toBe(true)
  rtc.resume()
  expect(element.muted).toBe(false)
  expect(fallback.calls).toEqual(['interrupt', 'resume'])
})

it('releases the connection, element and fallback on close', async () => {
  const { rtc, fallback, peer, element } = speaker()
  await rtc.connect(async () => 'server-answer')
  peer.ontrack?.({ streams: [{} as MediaStream] })
  rtc.close()
  expect(peer.closed).toBe(true)
  expect(element.srcObject).toBeNull()
  expect(fallback.calls).toContain('close')
})

it('reports the browser playout statistics of the received speech', async () => {
  const { rtc, peer } = speaker()
  const inbound = {
    type: 'inbound-rtp',
    kind: 'audio',
    concealedSamples: 960,
    totalSamplesReceived: 48000,
    jitterBufferDelay: 1.5,
    id: 'not-a-statistic',
  }
  Object.assign(peer, {
    getStats: async () =>
      new Map<string, Record<string, unknown>>([
        ['a', { type: 'transport' }],
        ['b', inbound],
      ]),
  })
  const reports: Record<string, number>[] = []
  await rtc.readStats((stats) => reports.push(stats))
  expect(reports).toEqual([
    { concealedSamples: 960, totalSamplesReceived: 48000, jitterBufferDelay: 1.5 },
  ])
})
