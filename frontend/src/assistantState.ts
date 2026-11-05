export interface VoiceMessage {
  role: 'user' | 'assistant'
  text: string
  turnId?: string
  partial?: boolean
}
export type AssistantPhase =
  'off' | 'connecting' | 'waiting' | 'listening' | 'speaking' | 'unavailable'

// Presentation only. Never use this grace period to gate microphone audio.
export class SpeakingIndicator {
  private timer: ReturnType<typeof setTimeout> | undefined
  private visible = false
  private changed: (speaking: boolean) => void

  constructor(changed: (speaking: boolean) => void) {
    this.changed = changed
  }

  update(playing: boolean) {
    clearTimeout(this.timer)
    if (playing) this.show(true)
    else if (this.visible) this.timer = setTimeout(() => this.show(false), 750)
  }

  reset() {
    clearTimeout(this.timer)
    this.show(false)
  }

  private show(value: boolean) {
    if (this.visible === value) return
    this.visible = value
    this.changed(value)
  }
}

export function assistantPhase(voice: {
  armed: boolean
  active: boolean
  busy: boolean
  locked: boolean
  speaking: boolean
  state: string
}): AssistantPhase {
  if (voice.busy) return 'connecting'
  if (!voice.armed) return 'off'
  if (voice.speaking) return 'speaking'
  if (voice.state === 'unavailable') return 'unavailable'
  if (voice.state === 'connecting') return 'connecting'
  if (voice.active && voice.state === 'listening') return 'listening'
  return 'waiting'
}
export function appendTranscript(
  messages: VoiceMessage[],
  role: string | undefined,
  text: string,
  turnId?: string,
  partial = false,
) {
  if ((role !== 'user' && role !== 'assistant') || !text.trim()) return messages
  const message = {
    role,
    text: text.trim(),
    ...(turnId ? { turnId, partial } : {}),
  } as VoiceMessage
  if (turnId) {
    const existing = messages.findIndex((item) => item.turnId === turnId && item.role === role)
    if (existing >= 0) {
      return messages.map((item, index) => (index === existing ? message : item))
    }
  }
  return [...messages.slice(-5), message]
}
export function waveformLevels(samples: Uint8Array, count = 24) {
  return Array.from({ length: count }, (_, index) => {
    const start = Math.floor((index * samples.length) / count)
    const end = Math.floor(((index + 1) * samples.length) / count)
    let power = 0
    for (let i = start; i < end; i++) power += ((samples[i] - 128) / 128) ** 2
    return Math.min(1, Math.sqrt(power / Math.max(1, end - start)) * 3)
  })
}
