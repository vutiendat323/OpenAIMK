import { useEffect, useRef, useState } from 'react'
import Keyboard from 'react-simple-keyboard'
import 'react-simple-keyboard/build/css/index.css'
import { NO_OFFSET, clampOffset } from '../keyboardDrag'
import type { Box, Offset } from '../keyboardDrag'

export function VirtualKeyboard() {
  const [isOpen, setIsOpen] = useState(false)
  const [layoutName, setLayoutName] = useState('default')
  const [, setInputVal] = useState('')
  const activeInputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null)
  const keyboardRef = useRef<{ setInput: (input: string) => void } | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  // Staff or guests can drag the keyboard by its handle; the position lasts until the page
  // reloads or the window is resized.
  const [offset, setOffset] = useState<Offset>(NO_OFFSET)
  const dragRef = useRef<{
    pointerId: number
    x: number
    y: number
    origin: Offset
    base: Box
  } | null>(null)

  useEffect(() => {
    const reset = () => setOffset(NO_OFFSET)
    window.addEventListener('resize', reset)
    return () => window.removeEventListener('resize', reset)
  }, [])

  const openFor = (target: HTMLElement | null) => {
    if (!target || wrapperRef.current?.contains(target)) return
    if (
      (target instanceof HTMLInputElement &&
        ['text', 'search', 'tel', 'password', ''].includes(target.type) &&
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
  // Turned back on with Ctrl+Alt+K while a text field already has focus: that field never
  // fires another focus event, so the keyboard would stay hidden until another field is
  // touched (2026-11-05: "Ctrl+Alt+K a second time shows nothing").
  useEffect(() => {
    openFor(document.activeElement as HTMLElement | null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const handleFocusIn = (event: FocusEvent) => openFor(event.target as HTMLElement | null)

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
                ['text', 'search', 'tel', 'password', ''].includes(currentActive.type)) ||
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
            ['text', 'search', 'tel', 'password', ''].includes(target.type)) ||
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

  const startDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const box = wrapperRef.current?.getBoundingClientRect()
    if (!box || (event.pointerType === 'mouse' && event.button !== 0)) return
    dragRef.current = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      origin: offset,
      base: {
        left: box.left - offset.x,
        top: box.top - offset.y,
        width: box.width,
        height: box.height,
      },
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const moveDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    setOffset(
      clampOffset(
        drag.base,
        { x: drag.origin.x + event.clientX - drag.x, y: drag.origin.y + event.clientY - drag.y },
        { width: window.innerWidth, height: window.innerHeight },
      ),
    )
  }

  const endDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null
  }

  if (!isOpen) return null

  return (
    <div
      ref={wrapperRef}
      className="kiosk-keyboard-wrapper"
      role="region"
      aria-label="Bàn phím ảo Kiosk"
      style={{ translate: `${offset.x}px ${offset.y}px` }}
      onPointerDown={(e) => {
        // Prevent clicking keys from stealing focus from active input
        e.preventDefault()
      }}
    >
      <div
        className="kiosk-keyboard-handle"
        title="Kéo để di chuyển bàn phím (nhấn đúp để đặt lại)"
        aria-hidden="true"
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onDoubleClick={() => setOffset(NO_OFFSET)}
      />
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
