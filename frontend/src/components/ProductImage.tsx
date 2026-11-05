import { Coffee } from 'lucide-react'
import { useState } from 'react'
import type { ImageMap, MenuItem } from '../types'

export function ProductImage({
  item,
  images,
  eager = false,
}: {
  item: MenuItem
  images: ImageMap
  eager?: boolean
}) {
  const [failed, setFailed] = useState(false)
  const source = images[item.product_id || '']?.src
  return source && !failed ? (
    <img
      src={source}
      alt={item.name}
      loading={eager ? 'eager' : 'lazy'}
      decoding="async"
      width="520"
      height="520"
      onError={() => setFailed(true)}
    />
  ) : (
    <div className="image-placeholder" role="img" aria-label={item.name}>
      <Coffee strokeWidth={1.25} />
      <span>Trend Coffee</span>
    </div>
  )
}
