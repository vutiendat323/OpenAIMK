import { folded } from './api'
import type { MenuItem } from './types'

const normalize = (value: string) =>
  folded(value)
    .replace(/\bcafe\b/g, 'ca phe')
    .replace(/\s+/g, ' ')
    .trim()
export function filterMenu(items: MenuItem[], query: string) {
  const term = normalize(query)
  if (!term) return items
  const mentions = items.filter(
    (item) =>
      ` ${term} `.includes(` ${normalize(item.name)} `) ||
      new RegExp(
        `(^|[^a-z0-9])${normalize(item.name).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}($|[^a-z0-9])`,
      ).test(term),
  )
  if (mentions.length) return mentions
  const parts = term
    .split(/[,;+&\n]|\bva\b/)
    .map((part) => part.trim())
    .filter(Boolean)
  return items.filter((item) =>
    parts.some((part) =>
      part
        .split(' ')
        .every((word) => normalize(item.name + ' ' + (item.description || '')).includes(word)),
    ),
  )
}
