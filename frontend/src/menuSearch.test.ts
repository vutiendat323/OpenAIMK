import { expect, test } from 'vitest'
import { filterMenu } from './menuSearch'
import type { MenuItem } from './types'

const items = [
  { id: 'salt', name: 'Cà phê muối' },
  { id: 'milk', name: 'Cà phê sữa' },
  { id: 'tea', name: 'Trà Bắc' },
  { id: 'cake', name: 'Bánh Tiramisu' },
] as MenuItem[]

test('a search containing three drink names displays all three', () => {
  expect(filterMenu(items, 'cafe muoi, ca phe sua va tra bac').map((i) => i.id)).toEqual([
    'salt',
    'milk',
    'tea',
  ])
})

test('keyword searches still narrow the menu', () => {
  expect(filterMenu(items, 'cà phê').map((i) => i.id)).toEqual(['salt', 'milk'])
  expect(filterMenu(items, 'chưa có')).toEqual([])
})
