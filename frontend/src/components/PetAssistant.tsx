import { useEffect, useRef, useState } from 'react'
import { Mascot } from 'wobnimo'
import type { PetState } from '../petState'
import { volt, voltPalette } from './pet/volt'
import { boundPetPointer } from './pet/pointerBoundary'
import './pet/pet.css'

export default function PetAssistant({ state }: { state: PetState }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const mascot = useRef<Mascot | null>(null)
  const initialState = useRef(state)
  const celebrationTimer = useRef<number | undefined>(undefined)
  const [renderer, setRenderer] = useState<'loading' | 'webgl' | 'fallback'>('loading')

  useEffect(() => {
    if (!canvas.current) return
    let instance: Mascot
    try {
      instance = new Mascot(canvas.current, volt, {
        state: initialState.current,
        palette: voltPalette,
        maxPixelRatio: 1,
        framing: 1.05,
        floor: 0,
      })
    } catch {
      const failed = window.setTimeout(() => setRenderer('fallback'), 0)
      return () => window.clearTimeout(failed)
    }
    mascot.current = instance
    const unbindPointer = boundPetPointer(canvas.current)
    const timeout = window.setTimeout(() => {
      instance.pause()
      setRenderer('fallback')
    }, 10000)
    const offReady = instance.on('ready', () => {
      window.clearTimeout(timeout)
      setRenderer('webgl')
    })
    return () => {
      window.clearTimeout(timeout)
      window.clearTimeout(celebrationTimer.current)
      offReady()
      unbindPointer()
      instance.dispose()
      mascot.current = null
    }
  }, [])

  useEffect(() => {
    window.clearTimeout(celebrationTimer.current)
    mascot.current?.setState(state)
  }, [state])

  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragRef = useRef<{
    startX: number
    startY: number
    origX: number
    origY: number
    moved: boolean
    minX: number
    maxX: number
    minY: number
    maxY: number
  } | null>(null)

  function celebrate() {
    if (!mascot.current) return
    window.clearTimeout(celebrationTimer.current)
    mascot.current.setState('celebrating')
    celebrationTimer.current = window.setTimeout(() => mascot.current?.setState(state), 4000)
  }

  function handlePointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if (e.button !== 0) return
    const el = e.currentTarget
    const panel = el.closest<HTMLElement>('.avatar-assistant') || el.parentElement

    // Allow Volt to float up to the very top of the panel when dragged
    let minY = -280
    let maxY = 100
    let minX = -85
    let maxX = 85

    if (panel) {
      const panelRect = panel.getBoundingClientRect()
      const topTravel = Math.max(240, Math.round(panelRect.height * 0.48))
      minY = -topTravel
      const bottomTravel = Math.max(60, Math.round(panelRect.height * 0.18))
      maxY = Math.min(120, bottomTravel)
      const horizontalTravel = Math.max(65, Math.round(panelRect.width * 0.22))
      minX = -horizontalTravel
      maxX = horizontalTravel
    }

    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      origX: position.x,
      origY: position.y,
      moved: false,
      minX,
      maxX,
      minY,
      maxY,
    }
    setIsDragging(true)
    el.setPointerCapture(e.pointerId)
  }

  function handlePointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!dragRef.current) return
    const dx = e.clientX - dragRef.current.startX
    const dy = e.clientY - dragRef.current.startY
    if (!dragRef.current.moved && Math.hypot(dx, dy) > 4) {
      dragRef.current.moved = true
    }
    if (dragRef.current.moved) {
      const { minX, maxX, minY, maxY } = dragRef.current
      const nextX = Math.max(minX, Math.min(maxX, dragRef.current.origX + dx))
      const nextY = Math.max(minY, Math.min(maxY, dragRef.current.origY + dy))
      setPosition({ x: nextX, y: nextY })
    }
  }

  function handlePointerUp(e: React.PointerEvent<HTMLDivElement>) {
    if (!dragRef.current) return
    if (!dragRef.current.moved) {
      mascot.current?.poke()
    }
    dragRef.current = null
    setIsDragging(false)
    try {
      e.currentTarget.releasePointerCapture(e.pointerId)
    } catch {
      // Ignore if pointer capture was already released
    }
  }

  function handlePointerCancel() {
    dragRef.current = null
    setIsDragging(false)
  }

  return (
    <div
      className={`assistant-pet ${isDragging ? 'is-dragging' : ''}`}
      data-state={state}
      data-renderer={renderer}
      style={{
        transform: `translate3d(${position.x}px, ${position.y}px, 0)`,
      }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
      onDoubleClick={celebrate}
    >
      <div className="pet-floating-body">
        {renderer !== 'webgl' && (
          <img
            className="pet-fallback"
            src={`/pet/volt-${state}.webp`}
            alt="Volt"
            draggable={false}
          />
        )}
        <canvas ref={canvas} className="pet-webgl" hidden={renderer === 'fallback'} />
      </div>
    </div>
  )
}
