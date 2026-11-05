import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { Action, KioskState } from './state'
import type { Order, Quote } from './types'
import { usePreferences } from './usePreferences'
import { VoicePlayer } from './voiceAudio'
import { AvatarPlayer } from './avatarPlayer'
import { RtcSpeaker } from './speakerRtc'
import { RtcCamera } from './cameraRtc'
import type { VoiceAudio } from './voiceAudio'
import { appendTranscript, waveformLevels, SpeakingIndicator } from './assistantState'
import type { VoiceMessage } from './assistantState'

export interface KioskEvent extends Partial<KioskState> {
  type: string
  generation: number
  session_token?: string
  status?: string
  message?: string
  view?: string
  query?: string
  item_ids?: string[]
  quote?: Quote | null
  order?: Order
  role?: string
  text?: string
  turnId?: string
  partial?: boolean
  voice?: string | null
  local_available?: boolean
  locked?: boolean
  audio?: VoiceAudio
  // Without audio when the WebRTC speaker already plays the clip.
  announcement?: { text: string; audio: VoiceAudio | null } | null
  playing?: boolean
  id?: string
  error?: string
  result?: unknown
}
type CameraSource = 'local' | 'device'
interface Runtime {
  cameraSource: CameraSource
  socket: WebSocket | null
  stream: MediaStream | null
  context: AudioContext | null
  video: HTMLVideoElement | null
  worklet: AudioWorkletNode | null
  player: VoicePlayer | AvatarPlayer | RtcSpeaker | null
  camera: RtcCamera | null
  inputMeter: AnalyserNode | null
  outputMeter: AnalyserNode | null
  playing: boolean
  announcement: boolean
  locked: boolean
  timer: number
  generation: number
  active: boolean
  serial: number
  cameraWanted: boolean
  cameraPending: boolean
  sessionEpoch: number
  pending: Map<
    string,
    {
      resolve: (v: unknown) => void
      reject: (e: Error) => void
      timer: number
      guestBound: boolean
    }
  >
}
function storedVoice() {
  try {
    return localStorage.getItem('trendcoffee.voice') ?? 'maple'
  } catch {
    return 'maple'
  }
}
function saveVoice(voice: string) {
  try {
    localStorage.setItem('trendcoffee.voice', voice)
  } catch {
    /* The selection still works when browser storage is unavailable. */
  }
}
// Each browser keeps its own camera choice; one that never chose uses the kiosk camera.
function storedCameraSource(): CameraSource {
  try {
    return localStorage.getItem('trendcoffee.cameraSource') === 'device' ? 'device' : 'local'
  } catch {
    return 'local'
  }
}
function saveCameraSource(source: CameraSource) {
  try {
    localStorage.setItem('trendcoffee.cameraSource', source)
  } catch {
    /* The selection still works when browser storage is unavailable. */
  }
}
export function useKioskVoice(onEvent: (event: KioskEvent) => void, token = '') {
  const { character } = usePreferences()
  const [enabled, setEnabled] = useState(false)
  const [cameraSource, setStoredCameraSource] = useState<CameraSource>(storedCameraSource)
  function setCameraSource(source: CameraSource) {
    saveCameraSource(source)
    setStoredCameraSource(source)
  }
  const [voices, setVoices] = useState<string[]>([])
  const [selectedVoice, setSelectedVoice] = useState(storedVoice)
  const [currentVoice, setCurrentVoice] = useState('')
  const [voiceOptionsReady, setVoiceOptionsReady] = useState(false)
  const [voiceBusy, setVoiceBusy] = useState(false)
  const [avatarActions, setAvatarActions] = useState<string[]>([])
  const [armed, setArmed] = useState(false)
  const [active, setActive] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [locked, setLocked] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [messages, setMessages] = useState<VoiceMessage[]>([])
  const [speaking, setSpeaking] = useState(false)
  const speakingIndicator = useRef<SpeakingIndicator | null>(null)
  if (!speakingIndicator.current) speakingIndicator.current = new SpeakingIndicator(setSpeaking)
  const [avatarStatus, setAvatarStatus] = useState('')
  const [avatarStream, setAvatarStream] = useState<MediaStream | null>(null)
  const [state, setState] = useState('off')
  const autoArmAttempted = useRef(false)
  const reconnectTimer = useRef(0)
  const reconnectAttempts = useRef(0)
  const armRef = useRef(arm)
  useLayoutEffect(() => {
    armRef.current = arm
  })
  const callback = useRef(onEvent)
  const rt = useRef<Runtime>({
    cameraSource: storedCameraSource(),
    socket: null,
    stream: null,
    context: null,
    video: null,
    worklet: null,
    player: null,
    camera: null,
    inputMeter: null,
    outputMeter: null,
    playing: false,
    announcement: false,
    locked: false,
    timer: 0,
    generation: 0,
    active: false,
    serial: 0,
    cameraWanted: false,
    cameraPending: false,
    sessionEpoch: 0,
    pending: new Map(),
  })
  useLayoutEffect(() => {
    callback.current = onEvent
  }, [onEvent])
  useEffect(() => {
    let live = true
    fetch('/api/kiosk/status')
      .then((r) => r.json())
      .then(async (v) => {
        if (!live) return
        setEnabled(v.enabled === true)
        if (!v.enabled) return
        try {
          const response = await fetch('/api/kiosk/voices')
          if (!response.ok) throw new Error('voice_options_unavailable')
          const data = await response.json()
          if (
            !Array.isArray(data.voices) ||
            !data.voices.every((v: unknown) => typeof v === 'string')
          )
            throw new Error('invalid_voice_options')
          if (!live) return
          setVoices(data.voices)
          if (storedVoice() && !data.voices.includes(storedVoice())) {
            saveVoice('')
            setSelectedVoice('')
          }
        } catch {
          if (live) {
            setSelectedVoice('')
            setStatus('Chưa tải được danh sách giọng nói. Có thể dùng giọng mặc định.')
          }
        } finally {
          if (live) setVoiceOptionsReady(true)
        }
      })
      .catch(() => {})
    return () => {
      live = false
      shutdown(false)
    }
  }, [])
  useEffect(() => {
    if (!enabled || !token || !voiceOptionsReady || autoArmAttempted.current) return
    autoArmAttempted.current = true
    let live = true
    void navigator.permissions
      ?.query({ name: 'microphone' as PermissionName })
      .then((permission) => {
        if (live && permission.state === 'granted') void armRef.current(token)
      })
      .catch(() => {})
    return () => {
      live = false
    }
  }, [enabled, token, voiceOptionsReady])
  useEffect(() => {
    const resume = () => {
      if (rt.current.context?.state === 'suspended')
        void rt.current.context.resume().catch(() => {})
      const player = rt.current.player
      if (player instanceof RtcSpeaker) player.unlock()
    }
    window.addEventListener('pointerdown', resume)
    window.addEventListener('keydown', resume)
    return () => {
      window.removeEventListener('pointerdown', resume)
      window.removeEventListener('keydown', resume)
    }
  }, [])
  async function syncCamera(localAvailable: boolean) {
    const runtime = rt.current
    runtime.cameraWanted = runtime.cameraSource === 'device'
    if (!runtime.cameraWanted) {
      if (!localAvailable)
        setStatus('Camera tại kiosk chưa sẵn sàng. Tắt micro để chọn nguồn camera khác.')
      runtime.camera?.close()
      runtime.camera = null
      for (const track of runtime.stream?.getVideoTracks() || []) {
        runtime.stream?.removeTrack(track)
        track.stop()
      }
      runtime.video?.pause()
      if (runtime.video) runtime.video.srcObject = null
      return
    }
    if (runtime.cameraPending || runtime.stream?.getVideoTracks().length || !runtime.stream) return
    runtime.cameraPending = true
    const attempt = runtime.sessionEpoch
    try {
      const videoStream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 15, max: 20 } },
      })
      if (
        runtime.sessionEpoch !== attempt ||
        !runtime.cameraWanted ||
        !runtime.stream ||
        !runtime.video
      ) {
        videoStream.getTracks().forEach((track) => track.stop())
        return
      }
      videoStream.getVideoTracks().forEach((track) => runtime.stream!.addTrack(track))
      runtime.video.srcObject = videoStream
      await runtime.video.play()
      startRtcCamera()
    } catch {
      if (runtime.sessionEpoch === attempt && runtime.cameraWanted)
        setStatus('Chưa mở được camera thiết bị này. Kiểm tra quyền camera rồi thử lại.')
    } finally {
      if (runtime.sessionEpoch === attempt) runtime.cameraPending = false
    }
  }
  // Device camera over WebRTC; until it connects, captureCamera sends socket JPEGs.
  function startRtcCamera() {
    const runtime = rt.current
    const track = runtime.stream?.getVideoTracks()[0]
    if (
      runtime.camera ||
      !runtime.cameraWanted ||
      !track ||
      runtime.socket?.readyState !== WebSocket.OPEN
    )
      return
    const camera = new RtcCamera()
    runtime.camera = camera
    void camera
      .connect(track, async (sdp) => {
        const result = (await command({ type: 'camera_offer', sdp })) as { sdp?: unknown }
        if (typeof result?.sdp !== 'string') throw new Error('camera_answer_missing')
        return result.sdp
      })
      .then(() => {
        // The sender's numbers, so the kiosk log can tell where a stalled camera stopped.
        const timer = window.setInterval(() => {
          if (runtime.camera !== camera || runtime.socket?.readyState !== WebSocket.OPEN)
            return clearInterval(timer)
          void camera.readStats((stats) => send({ type: 'camera_stats', stats })).catch(() => {})
        }, 2000)
      })
      .catch(() => {
        // Socket JPEGs keep the camera working.
        if (runtime.camera !== camera) return
        camera.close()
        runtime.camera = null
      })
  }
  function send(message: object) {
    const runtime = rt.current
    if (runtime.socket?.readyState !== WebSocket.OPEN) throw new Error('Kết nối voice đã đóng.')
    runtime.socket.send(JSON.stringify({ generation: runtime.generation, ...message }))
  }
  function command(message: object): Promise<unknown> {
    const runtime = rt.current
    const id = String(++runtime.serial)
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => {
        runtime.pending.delete(id)
        reject(new Error('Trend chưa phản hồi. Bạn thử lại nhé.'))
      }, 25000)
      runtime.pending.set(id, {
        resolve,
        reject,
        timer,
        // Connection settings and the speaker connection outlive a guest.
        guestBound: !(
          'type' in message &&
          (message.type === 'voice_setting' ||
            message.type === 'speaker_offer' ||
            message.type === 'camera_offer')
        ),
      })
      try {
        send({ ...message, id })
      } catch (error) {
        clearTimeout(timer)
        runtime.pending.delete(id)
        reject(error instanceof Error ? error : new Error('Mất kết nối'))
      }
    })
  }
  async function changeVoice(voice: string) {
    if (voiceBusy || (voice && !voices.includes(voice))) return
    setVoiceBusy(true)
    try {
      if (rt.current.socket?.readyState === WebSocket.OPEN)
        await command({ type: 'voice_setting', voice: voice || null })
      saveVoice(voice)
      setSelectedVoice(voice)
    } catch {
      setStatus('Chưa đổi được giọng nói. Bạn thử lại nhé.')
    } finally {
      setVoiceBusy(false)
    }
  }
  function shutdown(notify = true) {
    speakingIndicator.current?.reset()
    clearTimeout(reconnectTimer.current)
    const runtime = rt.current
    runtime.sessionEpoch++
    setAvatarStream(null)
    setAvatarStatus('')
    setAvatarActions([])
    runtime.cameraWanted = false
    runtime.cameraPending = false
    runtime.camera?.close()
    runtime.camera = null
    runtime.player?.close()
    runtime.inputMeter?.disconnect()
    runtime.outputMeter?.disconnect()
    runtime.inputMeter = null
    runtime.outputMeter = null
    runtime.playing = false
    runtime.announcement = false
    runtime.locked = false
    runtime.worklet?.disconnect()
    runtime.worklet = null
    runtime.stream?.getTracks().forEach((track) => track.stop())
    runtime.stream = null
    runtime.video?.pause()
    if (runtime.video) runtime.video.srcObject = null
    runtime.video = null
    clearInterval(runtime.timer)
    runtime.socket?.close()
    runtime.socket = null
    void runtime.context?.close()
    runtime.context = null
    runtime.player = null
    for (const pending of runtime.pending.values()) {
      clearTimeout(pending.timer)
      pending.reject(new Error('Phiên voice đã kết thúc.'))
    }
    runtime.pending.clear()
    const wasActive = runtime.active
    runtime.active = false
    if (notify) {
      setArmed(false)
      setActive(false)
      setBusy(false)
      setLocked(false)
      setTranscript('')
      setMessages([])
      speakingIndicator.current?.reset()
      setState('off')
      setStatus('Đã tắt mic')
      if (wasActive) callback.current({ type: 'ended', generation: runtime.generation + 1 })
    }
  }
  async function arm(token: string) {
    if (rt.current.socket || busy) return
    clearTimeout(reconnectTimer.current)
    setBusy(true)
    setStatus('Đang kết nối…')
    const runtime = rt.current
    const attempt = ++runtime.sessionEpoch
    runtime.cameraSource = cameraSource
    runtime.cameraWanted = cameraSource === 'device'
    try {
      const context = new AudioContext({ sampleRate: 48000, latencyHint: 'interactive' })
      runtime.context = context
      void context.resume().catch(() => {})
      const audio = {
        channelCount: 1,
        echoCancellation: true,
        // Fusion handles speech filtering. Browser AGC can change the OS input
        // level and suppression can remove quiet Vietnamese word boundaries.
        noiseSuppression: false,
        autoGainControl: false,
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        audio,
        video:
          cameraSource === 'device'
            ? {
                facingMode: { ideal: 'user' },
                width: { ideal: 640 },
                height: { ideal: 480 },
                frameRate: { ideal: 15, max: 20 },
              }
            : false,
      })
      if (runtime.sessionEpoch !== attempt) {
        stream.getTracks().forEach((t) => t.stop())
        return
      }
      runtime.stream = stream
      const video = document.createElement('video')
      video.muted = true
      video.playsInline = true
      video.srcObject = stream
      runtime.video = video
      if (stream.getVideoTracks().length) await video.play()
      await context.audioWorklet.addModule('/voice-capture.js')
      if (runtime.sessionEpoch !== attempt) return
      const node = new AudioWorkletNode(context, 'trend-pcm-capture')
      runtime.worklet = node
      const source = context.createMediaStreamSource(stream)
      runtime.inputMeter = context.createAnalyser()
      runtime.inputMeter.fftSize = 256
      source.connect(runtime.inputMeter)
      source.connect(node)
      node.connect(context.destination)
      runtime.outputMeter = context.createAnalyser()
      runtime.outputMeter.fftSize = 256
      runtime.outputMeter.connect(context.destination)
      const showPlayback = (playing: boolean) => {
        runtime.playing = playing
        if (!playing) runtime.announcement = false
        speakingIndicator.current?.update(playing)
      }
      // Socket PCM playback: report the actual browser playout to the backend.
      const playback = (playing: boolean) => {
        if (runtime.sessionEpoch !== attempt) return
        showPlayback(playing)
        if (runtime.active && socket.readyState === WebSocket.OPEN) {
          try {
            send({ type: 'playback', playing })
          } catch {
            /* teardown */
          }
        }
      }
      const player =
        (character === 'avatar3d'
          ? await AvatarPlayer.create(
              context,
              token,
              playback,
              (stream) => {
                if (runtime.sessionEpoch === attempt) setAvatarStream(stream)
              },
              runtime.outputMeter,
              (state) => {
                if (runtime.sessionEpoch !== attempt) return
                setAvatarStatus(state === 'reconnecting' ? 'Đang kết nối lại avatar…' : '')
              },
            )
          : null) ??
        (character === 'pet'
          ? await RtcSpeaker.create(context, playback, runtime.outputMeter)
          : await VoicePlayer.create(context, playback, runtime.outputMeter))
      if (runtime.sessionEpoch !== attempt) {
        player.close()
        return
      }
      runtime.player = player
      setAvatarActions(player instanceof AvatarPlayer ? player.availableActions() : [])
      const socket = new WebSocket(
        `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/kiosk`,
      )
      runtime.socket = socket
      node.port.onmessage = ({
        data: captured,
      }: MessageEvent<{ generation: number; data: ArrayBuffer }>) => {
        if (captured.generation !== runtime.generation) return
        // AudioWorklet keeps its capture clock when background tab timers slow down.
        // Pump the camera even while waiting for a guest, before the mic-send guard.
        captureCamera()
        const data = captured.data
        if (
          !runtime.active ||
          socket.readyState !== WebSocket.OPEN ||
          socket.bufferedAmount > 65536
        )
          return
        const packet = new Uint8Array(5 + data.byteLength)
        packet[0] = 1
        new DataView(packet.buffer).setUint32(1, runtime.generation, true)
        packet.set(new Uint8Array(data), 5)
        socket.send(packet)
      }
      socket.onopen = () => {
        if (runtime.socket !== socket || runtime.sessionEpoch !== attempt) return
        // A restarted server begins numbering guests again from zero.
        runtime.generation = 0
        runtime.worklet?.port.postMessage({ generation: 0 })
        reconnectAttempts.current = 0
        socket.send(
          JSON.stringify({
            type: 'auth',
            session_token: token,
            camera_source: runtime.cameraSource,
            voice: selectedVoice || null,
          }),
        )
        const speaker = runtime.player
        if (speaker instanceof RtcSpeaker)
          void speaker
            .connect(async (sdp) => {
              const result = (await command({ type: 'speaker_offer', sdp })) as { sdp?: unknown }
              if (typeof result?.sdp !== 'string') throw new Error('speaker_answer_missing')
              return result.sdp
            })
            .then(() => {
              const timer = window.setInterval(() => {
                if (runtime.player !== speaker || socket.readyState !== WebSocket.OPEN)
                  return clearInterval(timer)
                void speaker
                  .readStats((stats) => send({ type: 'speaker_stats', stats }))
                  .catch(() => {})
              }, 2000)
            })
            .catch(() => {
              /* Socket PCM keeps playing through the fallback. */
            })
        startRtcCamera()
        setArmed(true)
        setBusy(false)
        setStatus(context.state === 'running' ? 'Sẵn sàng' : 'Chạm để bật âm thanh')
        setState('waiting')
      }
      socket.onmessage = ({ data }) => {
        if (runtime.socket !== socket || runtime.sessionEpoch !== attempt) return
        if (typeof data !== 'string' || data.length > 1000000) return
        const event = JSON.parse(data) as KioskEvent
        if (event.generation < runtime.generation) return
        if (event.type === 'session' || event.type === 'ended') {
          runtime.player?.stop()
          runtime.generation = event.generation
          runtime.worklet?.port.postMessage({ generation: event.generation })
          runtime.player?.resume()
          if (runtime.player instanceof AvatarPlayer) {
            if (event.type === 'session') runtime.player.action('wave')
          }
          runtime.active = event.type === 'session'
          setActive(runtime.active)
          if (event.type === 'session') setCurrentVoice(event.voice || '')
          setLocked(false)
          setTranscript('')
          setMessages([])
          runtime.locked = false
          speakingIndicator.current?.reset()
          setState(event.type === 'session' ? 'connecting' : 'waiting')
          for (const [id, pending] of runtime.pending) {
            if (!pending.guestBound) continue
            clearTimeout(pending.timer)
            pending.reject(new Error('Phiên khách đã thay đổi.'))
            runtime.pending.delete(id)
          }
          if (event.announcement) {
            runtime.announcement = true
            setTranscript(event.announcement.text)
            setMessages([{ role: 'assistant', text: event.announcement.text }])
            if (event.announcement.audio) runtime.player?.push(event.announcement.audio)
          }
        }
        if (event.type === 'result' || event.type === 'error') {
          const pending = runtime.pending.get(event.id || '')
          if (pending) {
            clearTimeout(pending.timer)
            runtime.pending.delete(event.id!)
            if (event.type === 'result') pending.resolve(event.result)
            else pending.reject(new Error(event.error || 'Chưa xử lý được yêu cầu.'))
          }
          return
        }
        if (event.type === 'camera' && typeof event.local_available === 'boolean')
          void syncCamera(event.local_available)
        if (event.type === 'camera_reset') {
          // The server saw this connection's video stop: socket JPEGs carry the camera until
          // a new connection is up.
          runtime.camera?.close()
          runtime.camera = null
          window.setTimeout(() => startRtcCamera(), 1000)
        }
        if (event.type === 'status') {
          setState(event.status || '')
          setStatus(event.message || '')
          if (event.status === 'unavailable') {
            setLocked(false)
            if (!runtime.announcement) runtime.player?.stop()
          }
        }
        if (
          event.type === 'announcement' &&
          event.announcement &&
          runtime.active &&
          event.generation === runtime.generation
        ) {
          runtime.announcement = true
          setTranscript(event.announcement.text)
          setMessages([{ role: 'assistant', text: event.announcement.text }])
          if (event.announcement.audio) runtime.player?.push(event.announcement.audio)
        }
        // The backend's speaker clock reports WebRTC playout; it already informed Fusion.
        if (event.type === 'speaking' && typeof event.playing === 'boolean')
          showPlayback(event.playing)
        if (event.type === 'sensor' && !('connected' in event && event.connected))
          setStatus('Chưa kết nối được Visual. Bạn vẫn có thể dùng màn hình.')
        if (event.type === 'fusion') {
          runtime.locked = event.locked === true
          setLocked(runtime.locked)
        }
        if (event.type === 'voice_turn' && runtime.player) {
          if (event.role === 'user') {
            runtime.player.interrupt()
            speakingIndicator.current?.reset()
          } else runtime.player.resume()
        }
        if (event.type === 'transcript') {
          setTranscript(event.text || '')
          setMessages((previous) =>
            appendTranscript(previous, event.role, event.text || '', event.turnId, event.partial),
          )
        }
        if (event.type === 'audio' && event.audio && runtime.active) {
          runtime.announcement = false
          try {
            runtime.player?.push(event.audio)
          } catch {
            setStatus('Phát âm thanh bị gián đoạn.')
            void command({ type: 'end' }).catch(() => {})
          }
        }
        if (event.type === 'warning') setStatus(event.message || '')
        if (event.type === 'ended') setStatus('Phiên đã kết thúc. Đang chờ khách tiếp theo.')
        callback.current(event)
      }
      socket.onclose = ({ code }) => {
        if (runtime.socket !== socket) return
        shutdown()
        if (code === 1008) return // authorization / another kiosk controller
        setState('connecting')
        setStatus('Đang kết nối lại giọng nói…')
        const delay = Math.min(500 * 2 ** reconnectAttempts.current, 8000)
        reconnectAttempts.current = Math.min(reconnectAttempts.current + 1, 4)
        reconnectTimer.current = window.setTimeout(() => void armRef.current(token), delay)
      }
      const cameraLive = () =>
        stream.getVideoTracks().some((track) => track.readyState === 'live' && !track.muted)
      const canvas = document.createElement('canvas')
      canvas.width = 640
      canvas.height = 480
      const drawing = canvas.getContext('2d')!
      let frame = -1,
        encoding = false,
        lastFrameAt = -Infinity
      function captureCamera() {
        const now = performance.now()
        if (
          socket.readyState !== WebSocket.OPEN ||
          socket.bufferedAmount > 65536 ||
          encoding ||
          !runtime.cameraWanted ||
          runtime.camera?.connected ||
          !cameraLive() ||
          video.readyState < 2 ||
          video.currentTime === frame ||
          now - lastFrameAt < 1000 / 15 - 1
        )
          return
        frame = video.currentTime
        lastFrameAt = now
        encoding = true
        drawing.drawImage(video, 0, 0, 640, 480)
        canvas.toBlob(
          async (blob) => {
            try {
              if (
                blob &&
                cameraLive() &&
                runtime.sessionEpoch === attempt &&
                socket.readyState === WebSocket.OPEN
              ) {
                const bytes = new Uint8Array(await blob.arrayBuffer())
                const packet = new Uint8Array(bytes.length + 1)
                packet[0] = 2
                packet.set(bytes, 1)
                socket.send(packet)
              }
            } finally {
              encoding = false
            }
          },
          'image/jpeg',
          0.65,
        )
      }
      runtime.timer = window.setInterval(captureCamera, 1000 / 15)
      stream.getAudioTracks().forEach((track) =>
        track.addEventListener(
          'ended',
          () => {
            if (runtime.sessionEpoch === attempt) shutdown()
          },
          { once: true },
        ),
      )
    } catch (error) {
      shutdown()
      setStatus(
        error instanceof Error && error.message.startsWith('avatar_')
          ? 'Chưa kết nối được avatar. Kiểm tra dịch vụ LiveTalking rồi bật micro lại.'
          : cameraSource === 'device'
            ? 'Chưa bật được camera và micro thiết bị. Kiểm tra quyền trình duyệt rồi thử lại.'
            : 'Chưa bật được micro. Kiểm tra quyền trình duyệt rồi thử lại.',
      )
    } finally {
      if (runtime.sessionEpoch === attempt && runtime.socket?.readyState !== WebSocket.CONNECTING)
        setBusy(false)
    }
  }
  return {
    enabled,
    cameraSource,
    setCameraSource,
    voices,
    selectedVoice,
    currentVoice,
    changeVoice,
    voiceBusy,
    voiceOptionsReady,
    armed,
    active,
    busy,
    status,
    locked,
    transcript,
    messages,
    speaking,
    avatarStream,
    avatarStatus,
    avatarActions,
    avatarAction: (action: 'idle' | 'wave' | 'smile') => {
      const player = rt.current.player
      if (player instanceof AvatarPlayer) player.action(action)
    },
    interrupt: () => {
      speakingIndicator.current?.reset()
      const player = rt.current.player
      player?.interrupt()
    },
    state,
    audioLevels: () => {
      const runtime = rt.current
      const meter = runtime.playing
        ? ((runtime.player instanceof RtcSpeaker ? runtime.player.meter : null) ??
          runtime.outputMeter)
        : runtime.active
          ? runtime.inputMeter
          : null
      if (!meter) return new Array<number>(24).fill(0)
      const samples = new Uint8Array(meter.fftSize)
      meter.getByteTimeDomainData(samples)
      return waveformLevels(samples)
    },
    arm,
    disarm: () => shutdown(),
    command,
    begin: () => send({ type: 'begin' }),
    end: () => send({ type: 'end' }),
    action: (action: Action) => command({ type: 'action', action }),
    isActive: () => rt.current.active,
    activity: () => {
      if (rt.current.active) {
        try {
          send({ type: 'activity' })
        } catch {
          /* disconnected */
        }
      }
    },
  }
}
