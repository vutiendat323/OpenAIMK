import type { MenuCategory, MenuItem, Order, Payment, Progress } from './types'
import type { KioskTimingInfo, TimingValues } from './kioskTiming'

const messages: Record<string, string> = {
  invalid_session: 'Phiên khách đã hết hạn. Bạn tải lại trang để bắt đầu lại.',
  stale_catalog: 'Thực đơn cần được nhân viên cập nhật trước khi đặt món.',
  catalog_changed: 'Giá hoặc món đã thay đổi. Bạn kiểm tra lại giỏ để nhận bản tạm tính mới nhé.',
  quote_expired: 'Bản tạm tính đã hết hạn. Bạn kiểm tra lại món và giá nhé.',
  fulfillment_required: 'Bạn chọn dùng tại quán hay mang đi nhé.',
  table_required: 'Bạn nhập số bàn để phục vụ đúng chỗ nhé.',
  no_available_tables: 'Quán hiện chưa có bàn trống. Bạn có thể chọn mang đi nhé.',
  live_tables_unavailable: 'Chưa lấy được tình trạng bàn trực tiếp từ quán.',
  merchant_table_not_found: 'Không tìm thấy bàn này trong danh sách hiện tại của quán.',
  merchant_unreachable: 'Chưa kết nối được với quán. Bạn thử lại nhé.',
  merchant_rejected: 'Quán chưa trả được dữ liệu hiện tại. Bạn thử lại nhé.',
  sold_out: 'Món này đang hết. Bạn chọn món khác nhé.',
  invalid_options: 'Tùy chọn này chưa được hỗ trợ.',
  quantity_limit: 'Mỗi yêu cầu tối đa 100 món.',
  staff_forbidden: 'Mã nhân viên không đúng.',
  staff_disabled: 'Server chưa bật mã nhân viên (TREND_STAFF_TOKEN).',
  invalid_kiosk_timing: 'Có giá trị nằm ngoài giới hạn cho phép.',
}
export class ApiError extends Error {
  code: string
  constructor(code: string) {
    super(
      messages[code] ||
        'Chưa xử lý được yêu cầu. Bạn kiểm tra kết nối hoặc nhờ nhân viên hỗ trợ nhé.',
    )
    this.code = code
  }
}
async function request<T>(
  path: string,
  token = '',
  method = 'GET',
  data?: unknown,
  timeout = 8000,
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch('/api/' + path, {
      method,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: 'Bearer ' + token } : {}),
      },
      ...(data === undefined ? {} : { body: JSON.stringify(data) }),
    })
    const body = await response.json()
    if (!response.ok) throw new ApiError(body.error || 'invalid_request')
    return body as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new Error(
      'Kết nối chưa ổn định. Nếu vừa gửi yêu cầu, hãy kiểm tra tiến độ trước khi thử lại.',
    )
  } finally {
    clearTimeout(timer)
  }
}
export const api = {
  session: () => request<{ session_token: string }>('sessions', '', 'POST'),
  menu: () =>
    request<{ items: MenuItem[]; categories: MenuCategory[]; merchant_connected: boolean }>('menu'),
  tables: () =>
    request<{
      tables: {
        id: string
        name: string
        status: string
        available: boolean
        location: string
      }[]
      first_available: { name: string } | null
      available_count: number
      live: true
      fetched_at: string
    }>('tables'),
  checkout: (token: string, data: unknown) =>
    request<Order>('checkout', token, 'POST', data, 25000),
  payment: (token: string, orderId: string) =>
    request<Payment>(
      `orders/${encodeURIComponent(orderId)}/payment`,
      token,
      'GET',
      undefined,
      12000,
    ),
  progress: (token: string) => request<Progress>('progress', token),
  kioskTiming: () => request<KioskTimingInfo>('kiosk/timing'),
  saveKioskTiming: (staffCode: string, values: TimingValues) =>
    request<KioskTimingInfo & { applies: 'now' | 'next_guest' }>(
      'kiosk/timing',
      staffCode,
      'PUT',
      values,
    ),
}
export const money = (value: number) => new Intl.NumberFormat('vi-VN').format(value) + 'đ'
export const folded = (value: string) =>
  value
    .toLocaleLowerCase('vi')
    .replaceAll('đ', 'd')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
