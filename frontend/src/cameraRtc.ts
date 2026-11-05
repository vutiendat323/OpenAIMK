// The guest's own camera ("Camera thiết bị này") over WebRTC. The browser encodes
// and paces the video itself, outside this page's JavaScript thread, so throttled
// timers or a busy page cannot delay frames. The kiosk socket's JPEG packets are
// only the fallback while this connection is not established.
export class RtcCamera {
  private peer: RTCPeerConnection
  private closed = false

  constructor(createPeer = () => new RTCPeerConnection({ iceServers: [] })) {
    this.peer = createPeer()
  }

  get connected() {
    return !this.closed && this.peer.connectionState === 'connected'
  }

  async connect(track: MediaStreamTrack, negotiate: (sdp: string) => Promise<string>) {
    const peer = this.peer
    peer.addTransceiver(track, {
      direction: 'sendonly',
      // Like the kiosk's own C920 (2026-11-05: 12-16 fps here against 29-30 there). Visual
      // still analyses at most 15 frames per second, always from the newest frame.
      sendEncodings: [{ maxFramerate: 30, maxBitrate: 2_000_000 }],
    })
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

  /** The browser's own sender numbers, to tell a browser that stopped sending from a
   *  server that stopped receiving (2026-11-05: 34 frames, then none). */
  async readStats(report: (stats: Record<string, number | string>) => void) {
    if (this.closed) return
    const stats = await this.peer.getStats()
    stats.forEach((entry: Record<string, unknown>) => {
      if (entry.type !== 'outbound-rtp' || entry.kind !== 'video') return
      const values: Record<string, number | string> = {}
      for (const [key, value] of Object.entries(entry))
        if (typeof value === 'number' && key !== 'timestamp' && key !== 'ssrc') values[key] = value
      if (typeof entry.qualityLimitationReason === 'string')
        values.qualityLimitationReason = entry.qualityLimitationReason
      report(values)
    })
  }

  close() {
    this.closed = true
    this.peer.close()
  }
}
