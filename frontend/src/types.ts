export type Fulfillment = '' | 'takeaway' | 'at_table'
export type Options = Record<string, string>
export interface MenuCategory {
  id: string
  name: string
}
export interface MenuItem {
  id: string
  product_id?: string
  name: string
  description?: string
  category: string
  category_id?: string
  is_top_sell?: boolean
  is_new?: boolean
  variant_name?: string
  price_vnd: number
  options: Record<string, string[]>
  availability: string
  stale: boolean
  source_url: string
  verified_at: string
}
export interface CartLine {
  key: string
  item: MenuItem
  quantity: number
  options: Options
  note?: string
}
export interface PricedLine {
  item_id: string
  name: string
  quantity: number
  options: Options
  note?: string
  unit_price_vnd: number
  subtotal_vnd: number
}
export interface Quote {
  id: string
  confirmation_token: string
  lines: PricedLine[]
  total_vnd: number
  fulfillment: Exclude<Fulfillment, ''>
  table_label: string | null
  order_note?: string
  notice: string
  expires_at: number
  mode?: 'merchant_api' | 'local_queue_only'
  vibrating_card?: number
}
export interface Order extends Omit<Quote, 'confirmation_token' | 'expires_at'> {
  status: string
  payment_status: string
  created_at: string
  delivery: string
  merchant?: { state: string; order_slug?: string; error?: string }
  payment?: Payment
}
export interface Payment {
  order_id?: string
  merchant_order_id?: string
  amount_vnd?: number
  expires_at?: number
  status: string
  qr_image?: string | null
  payment_connected?: boolean
  vibrating_card?: number | null
}
export interface Handoff {
  id: string
  reason: string
  status: string
  delivered: boolean
  created_at: string
}
export interface Progress {
  orders: Order[]
  handoffs: Handoff[]
  events: { id: number; entity: string; type: string; created_at: string }[]
  mode: string
}
export type ImageMap = Record<string, { src: string; source_url: string; name: string }>
