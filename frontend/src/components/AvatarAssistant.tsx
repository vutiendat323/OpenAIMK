import { lazy, Suspense } from 'react'
import { petState } from '../petState'
import { usePreferences } from '../usePreferences'
import { useEffect, useRef, useState } from 'react'
import { Mic, MicOff } from 'lucide-react'
import { Button } from './ui/button'
import { assistantPhase } from '../assistantState'
import type { useKioskVoice } from '../useKioskVoice'

const PetAssistant = lazy(() => import('./PetAssistant'))

type Voice = ReturnType<typeof useKioskVoice>
const labels = {
  off: 'Đã tắt mic',
  connecting: 'Đang kết nối',
  waiting: 'Sẵn sàng',
  listening: 'Đang lắng nghe',
  speaking: 'Trend đang nói',
  unavailable: 'Tiếp tục trên màn hình',
}

function AudioWave({ read, active }: { read: () => number[]; active: boolean }) {
  const [levels, setLevels] = useState(new Array<number>(24).fill(0))
  const reader = useRef(read)
  useEffect(() => {
    reader.current = read
  }, [read])
  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => setLevels(reader.current()), 80)
    return () => clearInterval(timer)
  }, [active])
  return (
    <div className="assistant-wave" aria-hidden="true">
      {levels.map((value, index) => (
        <span key={index} style={{ height: `${4 + (active ? value : 0) * 27}px` }} />
      ))}
    </div>
  )
}

export function AvatarAssistant({ voice, token }: { voice: Voice; token: string }) {
  const { t, character } = usePreferences()
  const phase = assistantPhase(voice)
  const conversation = useRef<HTMLDivElement>(null)
  const avatarVideo = useRef<HTMLVideoElement>(null)
  useEffect(() => {
    const video = avatarVideo.current
    if (!video) return
    video.srcObject = voice.avatarStream
    if (voice.avatarStream) void video.play().catch(() => {})
    return () => {
      video.srcObject = null
    }
  }, [voice.avatarStream, character])
  useEffect(() => {
    const element = conversation.current
    if (element) element.scrollTop = element.scrollHeight
  }, [voice.messages])
  return (
    <aside className="assistant-column" aria-label={t('Trợ lý Trend')}>
      <svg width="0" height="0" aria-hidden="true" className="avatar-color-filter">
        <defs>
          <filter
            id="avatar-white-background"
            x="0"
            y="0"
            width="100%"
            height="100%"
            colorInterpolationFilters="sRGB"
          >
            <feFlood floodColor="#f4faef" result="backgroundKey" />
            <feBlend in="SourceGraphic" in2="backgroundKey" mode="difference" result="difference" />
            <feColorMatrix
              in="difference"
              type="matrix"
              values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  6 6 6 0 -0.7"
              result="foregroundMask"
            />
            <feComposite
              in="SourceGraphic"
              in2="foregroundMask"
              operator="in"
              result="foreground"
            />
            <feFlood floodColor="#ffffff" result="white" />
            <feComposite in="foreground" in2="white" operator="over" />
          </filter>
        </defs>
      </svg>
      <section
        className="avatar-assistant"
        data-phase={phase}
        data-engine={character === 'pet' ? 'pet' : 'livetalking'}
        data-character={character}
      >
        <header className="assistant-heading">
          <span className="assistant-phase" role="status">
            <i />
            {phase === 'speaking' || phase === 'listening'
              ? t(labels[phase])
              : t(voice.avatarStatus || voice.status || labels[phase])}
          </span>
        </header>
        <div className="assistant-scene">
          <div className="avatar-stage" aria-hidden="true">
            {character === 'pet' ? (
              <Suspense fallback={null}>
                <PetAssistant state={petState(phase)} />
              </Suspense>
            ) : (
              <>
                <video ref={avatarVideo} autoPlay playsInline muted hidden={!voice.avatarStream} />
                <img
                  style={{ display: voice.avatarStream ? 'none' : undefined }}
                  src="/avatars/trend-live.png"
                  alt=""
                  width="720"
                  height="1280"
                  fetchPriority="high"
                />
              </>
            )}
          </div>
        </div>
        <div
          className="assistant-conversation"
          ref={conversation}
          role="log"
          aria-label={t('Hội thoại bằng giọng nói')}
          aria-live="polite"
        >
          {voice.messages.slice(-2).map((message, index) => (
            <div className={'assistant-bubble ' + message.role} key={index}>
              <p>{message.text}</p>
            </div>
          ))}
        </div>
        <AudioWave
          read={voice.audioLevels}
          active={phase === 'listening' || phase === 'speaking'}
        />
        <div className="assistant-controls">
          {!voice.armed ? (
            <Button
              className="assistant-start"
              disabled={voice.busy || !token || !voice.voiceOptionsReady}
              onClick={() => void voice.arm(token)}
            >
              <Mic size={18} />
              {t(voice.busy ? 'Đang kết nối…' : 'Bật micro')}
            </Button>
          ) : (
            <div className="assistant-controls-row">
              <Button className="assistant-disarm" onClick={voice.disarm}>
                <MicOff size={16} />
                {t('Tắt micro')}
              </Button>
              {!voice.active && (
                <Button className="assistant-start" onClick={() => voice.begin()}>
                  <Mic size={16} />
                  {t('Bắt đầu nói')}
                </Button>
              )}
            </div>
          )}
        </div>
      </section>
    </aside>
  )
}
