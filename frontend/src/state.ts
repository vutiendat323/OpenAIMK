import type { CartLine, Fulfillment, MenuItem, Options, Quote } from './types'

export interface KioskState {
  cart: CartLine[]
  fulfillment: Fulfillment
  tableLabel: string
  orderNote: string
  quote: Quote | null
  revision: number
}
export const initialState = (): KioskState => ({
  cart: [],
  fulfillment: '',
  tableLabel: '',
  orderNote: '',
  quote: null,
  revision: 0,
})
export type Action =
  | { type: 'hydrate'; state: KioskState; newGuest?: boolean }
  | { type: 'add'; item: MenuItem; quantity: number; options: Options }
  | { type: 'quantity'; key: string; value: number }
  | { type: 'remove'; key: string }
  | { type: 'line_note'; key: string; value: string }
  | { type: 'order_note'; value: string }
  | { type: 'fulfillment'; value: Fulfillment }
  | { type: 'table'; value: string }
  | { type: 'quote'; quote: Quote; revision: number }
  | { type: 'clear' }
  | { type: 'reset' }

const validQuantity = (n: number) => Number.isInteger(n) && n >= 1 && n <= 100
const signature = (id: string, options: Options, note = '') =>
  id + JSON.stringify([Object.entries(options).sort(), note.trim()])
export function reducer(state: KioskState, action: Action): KioskState {
  if (action.type === 'hydrate')
    return action.newGuest || action.state.revision >= state.revision ? action.state : state
  if (action.type === 'quote')
    return action.revision === state.revision ? { ...state, quote: action.quote } : state
  if (action.type === 'reset') return { ...initialState(), revision: state.revision + 1 }
  if (action.type === 'clear')
    return { ...state, cart: [], orderNote: '', quote: null, revision: state.revision + 1 }
  let next = state
  switch (action.type) {
    case 'add': {
      if (!validQuantity(action.quantity)) return state
      const identity = signature(action.item.id, action.options)
      const key = `${identity}#${state.revision + 1}`
      const existing = state.cart.find(
        (line) => signature(line.item.id, line.options, (line.note || '').trim()) === identity,
      )
      if (existing && !validQuantity(existing.quantity + action.quantity)) return state
      const cart = existing
        ? state.cart.map((line) =>
            line.key === existing.key
              ? { ...line, quantity: line.quantity + action.quantity }
              : line,
          )
        : [
            ...state.cart,
            {
              key,
              item: action.item,
              quantity: action.quantity,
              options: action.options,
              note: '',
            },
          ]
      if (cart.reduce((sum, line) => sum + line.quantity, 0) > 100 || cart.length > 20) return state
      next = { ...state, cart }
      break
    }
    case 'quantity':
      if (
        !validQuantity(action.value) ||
        state.cart.every((line) => line.key !== action.key || line.quantity === action.value)
      )
        return state
      if (
        state.cart.reduce(
          (sum, line) => sum + (line.key === action.key ? action.value : line.quantity),
          0,
        ) > 100
      )
        return state
      next = {
        ...state,
        cart: state.cart.map((line) =>
          line.key === action.key ? { ...line, quantity: action.value } : line,
        ),
      }
      break
    case 'remove': {
      const cart = state.cart.filter((line) => line.key !== action.key)
      next = { ...state, cart, orderNote: cart.length ? state.orderNote : '' }
      break
    }
    case 'line_note': {
      if (action.value.length > 300) return state
      if (state.cart.every((line) => line.key !== action.key || line.note === action.value))
        return state
      const cart = state.cart.map((line) => {
        if (line.key !== action.key) return line
        return { ...line, note: action.value }
      })
      next = { ...state, cart }
      break
    }
    case 'order_note':
      if (action.value.length > 1000) return state
      if (state.orderNote === action.value) return state
      next = { ...state, orderNote: action.value }
      break
    case 'fulfillment':
      if (state.fulfillment === action.value) return state
      next = {
        ...state,
        fulfillment: action.value,
        tableLabel: action.value === 'takeaway' ? '' : state.tableLabel,
      }
      break
    case 'table':
      if (state.tableLabel === action.value) return state
      next = { ...state, tableLabel: action.value }
      break
  }
  return { ...next, quote: null, revision: state.revision + 1 }
}
