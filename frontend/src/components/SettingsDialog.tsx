import { useState } from 'react'
import {
  Check,
  ChevronDown,
  Database,
  Info,
  Monitor,
  Moon,
  Settings,
  Sun,
  Timer,
  UserRound,
  X,
} from 'lucide-react'
import { Select } from 'radix-ui'
import { getNonce } from 'get-nonce'
import { Button } from './ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from './ui/dialog'
import { usePreferences } from '../usePreferences'
import { KioskTimingSettings } from './KioskTimingSettings'
import type { useKioskVoice } from '../useKioskVoice'

const sections = [
  { id: 'general', label: 'Chung', icon: Settings },
  { id: 'kiosk', label: 'Kiosk', icon: Timer },
  { id: 'profile', label: 'Hồ sơ', icon: UserRound },
  { id: 'data', label: 'Dữ liệu', icon: Database },
  { id: 'about', label: 'Giới thiệu', icon: Info },
] as const
const themes = [
  { value: 'light', label: 'Sáng', icon: Sun },
  { value: 'dark', label: 'Tối', icon: Moon },
  { value: 'system', label: 'Hệ thống', icon: Monitor },
] as const

function SettingsSelect({
  label,
  value,
  onValueChange,
  options,
  disabled = false,
  className = '',
}: {
  label: string
  value: string
  onValueChange: (value: string) => void
  options: { value: string; label: string }[]
  disabled?: boolean
  className?: string
}) {
  // Radix reserves an empty item value; the native default voice uses an empty string.
  const defaultValue = '__default__'
  return (
    <Select.Root
      value={value || defaultValue}
      disabled={disabled}
      onValueChange={(next) => onValueChange(next === defaultValue ? '' : next)}
    >
      <Select.Trigger
        className={'settings-picker settings-select-trigger ' + className}
        aria-label={label}
      >
        <Select.Value />
        <Select.Icon>
          <ChevronDown size={16} />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          className="settings-select-menu"
          position="popper"
          align="start"
          sideOffset={4}
          collisionPadding={12}
        >
          <Select.Viewport className="settings-select-viewport" nonce={getNonce()}>
            {options.map((option) => (
              <Select.Item
                className="settings-select-option"
                key={option.value}
                value={option.value || defaultValue}
              >
                <Select.ItemText>{option.label}</Select.ItemText>
                <Select.ItemIndicator className="settings-select-check">
                  <Check size={16} />
                </Select.ItemIndicator>
              </Select.Item>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  )
}

export function SettingsDialog({ voice }: { voice: ReturnType<typeof useKioskVoice> }) {
  const { theme, language, character, setTheme, setLanguage, setCharacter, t } = usePreferences()
  const [section, setSection] = useState<(typeof sections)[number]['id']>('general')
  return (
    <Dialog
      onOpenChange={(open) => {
        if (open) setSection('general')
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" className="header-tool settings-tool" aria-label={t('Cài đặt')}>
          <Settings size={18} />
        </Button>
      </DialogTrigger>
      <DialogContent
        className="settings-dialog"
        overlayClassName="settings-overlay"
        showCloseButton={false}
      >
        <header className="settings-header">
          <DialogTitle>{t('Cài đặt')}</DialogTitle>
          <DialogDescription className="sr-only">
            {t('Tùy chỉnh giao diện, ngôn ngữ, giọng nói và camera.')}
          </DialogDescription>
          <DialogClose asChild>
            <button className="settings-close" type="button" aria-label={t('Đóng')}>
              <X size={18} />
            </button>
          </DialogClose>
        </header>
        <div className="settings-body">
          <nav className="settings-sidebar" aria-label={t('Mục cài đặt')}>
            {sections.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                aria-pressed={section === id}
                onClick={() => setSection(id)}
              >
                <Icon size={18} strokeWidth={1.7} />
                {t(label)}
              </button>
            ))}
          </nav>
          <section
            className="settings-content"
            aria-label={t(sections.find(({ id }) => id === section)!.label)}
          >
            {section === 'general' && (
              <>
                <div className="settings-theme" role="group" aria-label={t('Giao diện')}>
                  <p>{t('Giao diện')}</p>
                  <div className="settings-theme-options">
                    {themes.map(({ value, label, icon: Icon }) => (
                      <button
                        key={value}
                        type="button"
                        aria-pressed={theme === value}
                        onClick={() => setTheme(value)}
                      >
                        <Icon size={18} strokeWidth={1.6} />
                        {t(label)}
                      </button>
                    ))}
                  </div>
                </div>
                <label className="settings-row">
                  <span>{t('Ngôn ngữ')}</span>
                  <SettingsSelect
                    className="settings-language"
                    label={t('Ngôn ngữ')}
                    value={language}
                    onValueChange={(value) => setLanguage(value === 'en' ? 'en' : 'vi')}
                    options={[
                      { value: 'vi', label: 'Tiếng Việt' },
                      { value: 'en', label: 'English' },
                    ]}
                  />
                </label>
                <label className="settings-row">
                  <span>{t('Nhân vật')}</span>
                  <SettingsSelect
                    label={t('Nhân vật')}
                    value={character}
                    disabled={voice.armed || voice.busy}
                    onValueChange={(value) => setCharacter(value === 'pet' ? 'pet' : 'avatar3d')}
                    options={[
                      { value: 'avatar3d', label: 'Avatar 3D' },
                      { value: 'pet', label: 'Pet' },
                    ]}
                  />
                </label>
                {voice.armed && (
                  <p className="settings-hint">{t('Tắt micro trước khi đổi nhân vật.')}</p>
                )}
                <label className="settings-row">
                  <span>{t('Giọng nói')}</span>
                  <SettingsSelect
                    className="settings-voice"
                    label={t('Giọng nói')}
                    value={voice.selectedVoice}
                    disabled={voice.busy || voice.voiceBusy || !voice.voiceOptionsReady}
                    onValueChange={(value) => void voice.changeVoice(value)}
                    options={[
                      { value: '', label: t('Mặc định Codex') },
                      ...voice.voices.map((name) => ({
                        value: name,
                        label: name.charAt(0).toUpperCase() + name.slice(1),
                      })),
                    ]}
                  />
                </label>
                {voice.active && voice.selectedVoice !== voice.currentVoice && (
                  <p className="settings-hint" role="status">
                    {t('Giọng mới áp dụng từ phiên tiếp theo.')}
                  </p>
                )}
                <label className="settings-row settings-camera-row">
                  <span>{t('Nguồn camera')}</span>
                  <SettingsSelect
                    className="settings-camera-picker"
                    label={t('Nguồn camera')}
                    value={voice.cameraSource}
                    disabled={voice.armed || voice.busy}
                    onValueChange={(value) =>
                      voice.setCameraSource(value === 'device' ? 'device' : 'local')
                    }
                    options={[
                      { value: 'local', label: t('Camera tại kiosk') },
                      { value: 'device', label: t('Camera thiết bị này') },
                    ]}
                  />
                </label>
                {voice.armed && (
                  <p className="settings-hint">{t('Tắt micro trước khi đổi nguồn camera.')}</p>
                )}
                {voice.armed && voice.avatarActions.length > 0 && (
                  <div className="settings-row">
                    <span>{t('Động tác avatar')}</span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {(['wave', 'smile', 'idle'] as const)
                        .filter((action) => voice.avatarActions.includes(action))
                        .map((action) => (
                          <Button
                            key={action}
                            variant="outline"
                            size="sm"
                            onClick={() => voice.avatarAction(action)}
                          >
                            {t({ wave: 'Vẫy tay', smile: 'Mỉm cười', idle: 'Đứng chờ' }[action])}
                          </Button>
                        ))}
                    </div>
                  </div>
                )}
              </>
            )}
            {section === 'kiosk' && <KioskTimingSettings />}
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}
