/** Register after Mascot so its global pointer handler runs before this boundary. */
export function boundPetPointer(canvas: Pick<HTMLCanvasElement, 'getBoundingClientRect'>) {
  // Wobnimo 0.2 has no pointer-radius setting. Use its existing leave event to
  // resume autonomous motion, without touching its source or blocking page input.
  const clear = () => document.dispatchEvent(new Event('pointerleave'))
  const constrain = (event: PointerEvent) => {
    const rect = canvas.getBoundingClientRect()
    const margin = 24
    if (
      event.clientX < rect.left - margin ||
      event.clientX > rect.right + margin ||
      event.clientY < rect.top - margin ||
      event.clientY > rect.bottom + margin
    ) {
      clear()
    }
  }
  window.addEventListener('pointermove', constrain, { passive: true })
  window.addEventListener('blur', clear)
  return () => {
    window.removeEventListener('pointermove', constrain)
    window.removeEventListener('blur', clear)
  }
}
