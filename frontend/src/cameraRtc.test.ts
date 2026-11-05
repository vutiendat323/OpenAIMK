import { expect, it } from 'vitest'
import { RtcCamera } from './cameraRtc'

class FakePeer {
  iceGatheringState = 'complete'
  connectionState = 'new'
  onicegatheringstatechange: (() => void) | null = null
  localDescription: { sdp: string } | null = null
  remote: { type: string; sdp: string } | null = null
  transceivers: { track: unknown; init: RTCRtpTransceiverInit }[] = []
  closed = false
  addTransceiver(track: unknown, init: RTCRtpTransceiverInit) {
    this.transceivers.push({ track, init })
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
  async getStats() {
    return new Map<string, Record<string, unknown>>([
      ['a', { type: 'inbound-rtp', kind: 'video', framesDecoded: 9 }],
      [
        'b',
        {
          type: 'outbound-rtp',
          kind: 'video',
          framesSent: 34,
          ssrc: 7,
          timestamp: 1,
          qualityLimitationReason: 'cpu',
          mid: '0',
        },
      ],
    ])
  }
}

const track = { kind: 'video' } as MediaStreamTrack

function camera() {
  const peer = new FakePeer()
  const rtc = new RtcCamera(() => peer as unknown as RTCPeerConnection)
  return { rtc, peer }
}

it('sends the camera as send-only video at up to 30 frames per second', async () => {
  const { rtc, peer } = camera()
  const offers: string[] = []
  await rtc.connect(track, async (sdp) => {
    offers.push(sdp)
    return 'server-answer'
  })
  expect(peer.transceivers).toHaveLength(1)
  expect(peer.transceivers[0].track).toBe(track)
  expect(peer.transceivers[0].init.direction).toBe('sendonly')
  expect(peer.transceivers[0].init.sendEncodings?.[0].maxFramerate).toBe(30)
  expect(offers).toEqual(['browser-offer'])
  expect(peer.remote).toEqual({ type: 'answer', sdp: 'server-answer' })
})

it('reports connected only while the connection is up', async () => {
  const { rtc, peer } = camera()
  expect(rtc.connected).toBe(false)
  await rtc.connect(track, async () => 'server-answer')
  peer.connectionState = 'connected'
  expect(rtc.connected).toBe(true)
  rtc.close()
  expect(peer.closed).toBe(true)
  expect(rtc.connected).toBe(false)
})

it('does not apply an answer after it was closed', async () => {
  const { rtc, peer } = camera()
  await rtc.connect(track, async () => {
    rtc.close()
    return 'late-answer'
  })
  expect(peer.remote).toBeNull()
})

it('waits for local candidates before sending the offer', async () => {
  const { rtc, peer } = camera()
  peer.iceGatheringState = 'gathering'
  let offered = false
  const connecting = rtc.connect(track, async () => {
    offered = true
    return 'server-answer'
  })
  await Promise.resolve()
  await Promise.resolve()
  expect(offered).toBe(false)
  peer.iceGatheringState = 'complete'
  peer.onicegatheringstatechange?.()
  await connecting
  expect(offered).toBe(true)
})

it('reports only the video sender numbers and its quality limit', async () => {
  const { rtc } = camera()
  const reports: Record<string, number | string>[] = []
  await rtc.readStats((stats) => reports.push(stats))
  expect(reports).toEqual([{ framesSent: 34, qualityLimitationReason: 'cpu' }])
})
