import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AvatarAssistant } from './AvatarAssistant'
import { PreferencesProvider } from '../preferences'
import type { useKioskVoice } from '../useKioskVoice'

const voice = {
  armed: false,
  busy: false,
  active: false,
  voiceOptionsReady: true,
  messages: [],
  avatarStream: null,
  avatarStatus: '',
  status: '',
  audioLevels: () => [],
} as unknown as ReturnType<typeof useKioskVoice>

const render = (element: React.ReactElement) =>
  renderToString(<PreferencesProvider>{element}</PreferencesProvider>)

describe('AvatarAssistant microphone controls', () => {
  it('shows the microphone button unless staff hid it with Ctrl+Alt+S', () => {
    expect(render(<AvatarAssistant voice={voice} token="t" />)).toContain('assistant-start')
    expect(
      render(<AvatarAssistant voice={voice} token="t" controlsVisible={false} />),
    ).not.toContain('assistant-controls')
  })

  it('hides the turn-off and start-speaking buttons too while armed', () => {
    const armed = { ...voice, armed: true } as unknown as ReturnType<typeof useKioskVoice>
    const html = render(<AvatarAssistant voice={armed} token="t" controlsVisible={false} />)
    expect(html).not.toContain('assistant-disarm')
    expect(html).not.toContain('assistant-start')
  })
})
