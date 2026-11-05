import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import banner1 from '../../Category/ChatGPT Image Oct 30, 2026, 02_41_47 PM-1.png'
import banner2 from '../../Category/ChatGPT Image Oct 30, 2026, 02_41_48 PM-2.png'

const BANNERS = [
  {
    id: 'banner-1',
    src: banner1,
    alt: 'Trend Coffee — Đậm vị đã gu, Cà phê, Trà, Bánh ngon',
  },
  {
    id: 'banner-2',
    src: banner2,
    alt: 'Trend Coffee — Chill một chút, Nạp vị ngon, Bật mood vui',
  },
]

export function SeasonalBanner() {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isPaused, setIsPaused] = useState(false)
  const touchStartX = useRef<number | null>(null)
  const touchStartY = useRef<number | null>(null)
  const touchDeltaX = useRef<number>(0)
  const touchDeltaY = useRef<number>(0)

  // Auto-play timer: resets when user manually changes slide (currentIndex) or pauses
  useEffect(() => {
    if (isPaused) return
    const timer = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % BANNERS.length)
    }, 5000)

    return () => clearInterval(timer)
  }, [isPaused, currentIndex])

  const prevSlide = () => {
    setCurrentIndex((prev) => (prev - 1 + BANNERS.length) % BANNERS.length)
  }

  const nextSlide = () => {
    setCurrentIndex((prev) => (prev + 1) % BANNERS.length)
  }

  const handleTouchStart = (e: React.TouchEvent) => {
    setIsPaused(true)
    touchStartX.current = e.touches[0].clientX
    touchStartY.current = e.touches[0].clientY
    touchDeltaX.current = 0
    touchDeltaY.current = 0
  }

  const handleTouchMove = (e: React.TouchEvent) => {
    if (touchStartX.current !== null && touchStartY.current !== null) {
      touchDeltaX.current = e.touches[0].clientX - touchStartX.current
      touchDeltaY.current = e.touches[0].clientY - touchStartY.current
    }
  }

  const handleTouchEnd = () => {
    if (
      touchStartX.current !== null &&
      Math.abs(touchDeltaX.current) > Math.abs(touchDeltaY.current)
    ) {
      if (touchDeltaX.current < -40) {
        nextSlide()
      } else if (touchDeltaX.current > 40) {
        prevSlide()
      }
    }
    touchStartX.current = null
    touchStartY.current = null
    touchDeltaX.current = 0
    touchDeltaY.current = 0
    setIsPaused(false)
  }

  return (
    <div
      className="seasonal-banner"
      role="region"
      aria-roledescription="carousel"
      aria-label="Khuyến mãi đặc biệt"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'ArrowLeft') prevSlide()
        if (e.key === 'ArrowRight') nextSlide()
      }}
      onPointerEnter={(e) => {
        if (e.pointerType === 'mouse') setIsPaused(true)
      }}
      onPointerLeave={(e) => {
        if (e.pointerType === 'mouse') setIsPaused(false)
      }}
      onFocus={() => setIsPaused(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) {
          setIsPaused(false)
        }
      }}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={handleTouchEnd}
    >
      <div
        className="seasonal-banner-track"
        style={{ transform: `translateX(-${currentIndex * 100}%)` }}
      >
        {BANNERS.map((banner, idx) => (
          <div
            className="seasonal-banner-slide"
            key={banner.id}
            role="group"
            aria-roledescription="slide"
            aria-label={`${idx + 1} / ${BANNERS.length}`}
            aria-hidden={currentIndex !== idx ? true : undefined}
          >
            <img
              src={banner.src}
              alt={banner.alt}
              width={3172}
              height={496}
              fetchPriority={idx === 0 ? 'high' : 'auto'}
              draggable={false}
            />
          </div>
        ))}
      </div>

      <button
        type="button"
        className="seasonal-banner-nav seasonal-banner-prev"
        onClick={prevSlide}
        aria-label="Banner trước"
      >
        <ChevronLeft size={22} />
      </button>

      <button
        type="button"
        className="seasonal-banner-nav seasonal-banner-next"
        onClick={nextSlide}
        aria-label="Banner kế tiếp"
      >
        <ChevronRight size={22} />
      </button>

      <div className="seasonal-banner-dots" role="group" aria-label="Chọn banner hiển thị">
        {BANNERS.map((banner, idx) => (
          <button
            key={banner.id}
            type="button"
            aria-current={currentIndex === idx ? 'true' : undefined}
            aria-label={`Banner ${idx + 1}`}
            className={`seasonal-banner-dot ${currentIndex === idx ? 'active' : ''}`}
            onClick={() => setCurrentIndex(idx)}
          />
        ))}
      </div>
    </div>
  )
}
