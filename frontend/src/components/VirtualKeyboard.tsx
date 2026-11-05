import { useEffect, useRef, useState } from 'react'
import Keyboard from 'react-simple-keyboard'
import 'react-simple-keyboard/build/css/index.css'

export function VirtualKeyboard() {
  const [isOpen, setIsOpen] = useState(false)
  const [layoutName, setLayoutName] = useState('default')
  const [, setInputVal] = useState('')
  const activeInputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null)
  const keyboardRef = useRef<{ setInput: (input: string) => void } | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleFocusIn = (event: FocusEvent) => {
      const target = event.target as HTMLElement | null
      if (!target) return
      if (wrapperRef.current?.contains(target)) return

      if (
        (target instanceof HTMLInputElement &&
          ['text', 'search', 'tel', ''].includes(target.type) &&
          !target.disabled &&
          !target.readOnly) ||
        (target instanceof HTMLTextAreaElement && !target.disabled && !target.readOnly)
      ) {
        activeInputRef.current = target
        setInputVal(target.value || '')
        keyboardRef.current?.setInput(target.value || '')
        setLayoutName('default')
        setIsOpen(true)
      }
    }

    const handleFocusOut = (event: FocusEvent) => {
      const nextTarget = event.relatedTarget as HTMLElement | null
      if (wrapperRef.current?.contains(nextTarget)) return

      setTimeout(() => {
        const currentActive = document.activeElement
        if (
          !currentActive ||
          (!wrapperRef.current?.contains(currentActive) &&
            !(
              (currentActive instanceof HTMLInputElement &&
                ['text', 'search', 'tel', ''].includes(currentActive.type)) ||
              currentActive instanceof HTMLTextAreaElement
            ))
        ) {
          setIsOpen(false)
        }
      }, 120)
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null
      if (!target) return

      if (
        isOpen &&
        wrapperRef.current &&
        !wrapperRef.current.contains(target) &&
        target !== activeInputRef.current &&
        !activeInputRef.current?.contains(target)
      ) {
        if (!(
          (target instanceof HTMLInputElement &&
            ['text', 'search', 'tel', ''].includes(target.type)) ||
          target instanceof HTMLTextAreaElement
        )) {
          setIsOpen(false)
        }
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false)
        activeInputRef.current?.blur()
      }
    }

    document.addEventListener('focusin', handleFocusIn)
    document.addEventListener('focusout', handleFocusOut)
    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('focusin', handleFocusIn)
      document.removeEventListener('focusout', handleFocusOut)
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  const onChange = (input: string) => {
    setInputVal(input)
    if (!activeInputRef.current) return

    const maxLength = activeInputRef.current.maxLength
    let nextVal = input
    if (maxLength && maxLength > 0 && nextVal.length > maxLength) {
      nextVal = nextVal.slice(0, maxLength)
      keyboardRef.current?.setInput(nextVal)
      setInputVal(nextVal)
    }

    const prototype =
      activeInputRef.current instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype
    const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set
    setter?.call(activeInputRef.current, nextVal)

    activeInputRef.current.dispatchEvent(new Event('input', { bubbles: true }))
    activeInputRef.current.dispatchEvent(new Event('change', { bubbles: true }))
  }

  const onKeyPress = (button: string) => {
    if (button === '{shift}' || button === '{lock}') {
      setLayoutName((prev) => (prev === 'default' ? 'shift' : 'default'))
    }
    if (button === '{enter}') {
      setIsOpen(false)
      activeInputRef.current?.blur()
    }
  }

  if (!isOpen) return null

  return (
    <div
      ref={wrapperRef}
      className="kiosk-keyboard-wrapper"
      role="region"
      aria-label="Bàn phím ảo Kiosk"
      onPointerDown={(e) => {
        // Prevent clicking keys from stealing focus from active input
        e.preventDefault()
      }}
    >
      <Keyboard
        keyboardRef={(r) => {
          keyboardRef.current = r
        }}
        layoutName={layoutName}
        mergeDisplay={true}
        display={{ '{space}': 'space' }}
        onChange={onChange}
        onKeyPress={onKeyPress}
      />
    </div>
  )
}
