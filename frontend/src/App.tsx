import { useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState } from 'react'
import {
  AlertCircle,
  ChevronUp,
  ClipboardList,
  Menu,
  QrCode,
  Search,
  ShoppingCart,
  X,
} from 'lucide-react'
import { Button } from './components/ui/button'
import { Input } from './components/ui/input'
import { ProductImage } from './components/ProductImage'
import { Cart } from './components/Cart'
import { ProductPanel, CheckoutResult } from './components/OrderDialogs'
import { ProgressPanel } from './components/ProgressPanel'
import { PaymentQr } from './components/PaymentQr'
import { AvatarAssistant } from './components/AvatarAssistant'
import { SettingsDialog } from './components/SettingsDialog'
import { VirtualKeyboard } from './components/VirtualKeyboard'
import { matchShortcut, saveShown, storedShown } from './kioskShortcuts'
import { DEFAULT_IDLE_SECONDS, idleNoticeMs } from './kioskTiming'
import { usePreferences } from './usePreferences'
import { initialNavigation, navigationReducer } from './navigation'
import type { NavigationAction } from './navigation'
import { filterMenu } from './menuSearch'
import { ApiError, api, money } from './api'
import { initialState, reducer } from './state'
import type { Action, KioskState } from './state'
import { useKioskVoice } from './useKioskVoice'
import type { Fulfillment, ImageMap, MenuCategory, MenuItem, Options, Order } from './types'
import allCategory from '../Category/tat-ca-clean.png'
import bestSellerCategory from '../Category/Rising flame and star icon-2.png'
import smoothieCategory from '../Category/Fruit smoothie cup with apple-3.png'
import newCategory from '../Category/Evergreen three-star sparkle icon-4.png'
import cakeCategory from '../Category/Green layered cake slice with cherry-5.png'
import coffeeCategory from '../Category/Steaming green coffee cup icon-6.png'
import foodCategory from '../Category/Green chicken drumstick cutlery icon-7.png'
import sodaCategory from '../Category/Fizzy soda cup icon-8.png'
import beerCategory from '../Category/Foamy beer mug and wine glass-9.png'
import teaCategory from '../Category/Teapot and tea cup icon-10.png'
import customPriceCategory from '../Category/Restaurant kiosk price tag-11.png'
import cartBucket from '../Category/green-open-bucket-no-drumstick.png'
import halloweenLogo from '../Category/Haunted Trend Coffee logo-2.png'

const categoryIcons: Record<string, string> = {
  'cà phê': coffeeCategory,
  'món trà': teaCategory,
  'sinh tố': smoothieCategory,
  'món bánh': cakeCategory,
  'món ăn': foodCategory,
  'nước giải khát': sodaCategory,
  'bia/ rượu vang': beerCategory,
  'giá tùy chỉnh': customPriceCategory,
}
const errorText = (error: unknown) =>
  error instanceof Error ? error.message : 'Chưa xử lý được yêu cầu.'
export default function App() {
  const { t, language, character } = usePreferences()
  const [state, localDispatch] = useReducer(reducer, undefined, initialState)
  const stateRef = useRef(state)
  useLayoutEffect(() => {
    stateRef.current = state
  }, [state])
  const [items, setItems] = useState<MenuItem[]>([])
  const [catalogs, setCatalogs] = useState<MenuCategory[]>([])
  const [tables, setTables] = useState<
    { id: string; name: string; status: string; available: boolean; location: string }[]
  >([])
  const [tablesLoading, setTablesLoading] = useState(false)
  const [merchantConnected, setMerchantConnected] = useState(false)
  const [images, setImages] = useState<ImageMap>({})
  const [token, setToken] = useState('')
  const [generation, setGeneration] = useState(0)
  const [bootRevision, setBootRevision] = useState(0)
  const epoch = useRef(0)
  const [loading, setLoading] = useState(true)
  const [bootError, setBootError] = useState('')
  const [category, setCategory] = useState('all')
  const [query, setQuery] = useState('')
  const [voiceMenuIds, setVoiceMenuIds] = useState<string[] | null>(null)
  const [selected, setSelected] = useState<MenuItem | null>(null)
  const [navigation, navigate] = useReducer(navigationReducer, initialNavigation)
  const [sidebarWidth, setSidebarWidth] = useState(440)
  const navigationButton = useRef<HTMLButtonElement>(null)
  const sidebar = useRef<HTMLElement>(null)
  function showView(view: NavigationAction) {
    setSelected(null)
    navigate(view)
    if (view === 'menu') navigationButton.current?.focus()
  }
  function closeSidebar() {
    navigate('close')
    navigationButton.current?.focus()
  }
  const progress = navigation.open && navigation.view === 'progress'
  useEffect(() => {
    if (!navigation.open) return
    const onKey = (event: KeyboardEvent) => {
      if (
        event.key === 'Escape' &&
        !event.defaultPrevented &&
        !document.querySelector('[role="dialog"], [role="listbox"]')
      ) {
        event.preventDefault()
        closeSidebar()
      }
    }
    window.addEventListener('keydown', onKey)
    sidebar.current?.focus({ preventScroll: true })
    return () => window.removeEventListener('keydown', onKey)
  }, [navigation.open, navigation.view])
  const [settingsVisible, setSettingsVisible] = useState(() => storedShown('settings'))
  const [keyboardEnabled, setKeyboardEnabled] = useState(() => storedShown('keyboard'))
  useEffect(() => {
    // Staff shortcuts: Ctrl+Alt+S hides/shows the Settings button; Ctrl+Alt+K turns the
    // on-screen keyboard off/on (for example while testing with a physical keyboard).
    const onKey = (event: KeyboardEvent) => {
      const shortcut = matchShortcut(event)
      if (!shortcut) return
      event.preventDefault()
      if (shortcut === 'settings') setSettingsVisible((visible) => !visible)
      else setKeyboardEnabled((enabled) => !enabled)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  useEffect(() => saveShown('settings', settingsVisible), [settingsVisible])
  useEffect(() => saveShown('keyboard', keyboardEnabled), [keyboardEnabled])
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState<Order | null>(null)
  const [error, setError] = useState('')
  const [idle, setIdle] = useState(false)
  const [showScrollTop, setShowScrollTop] = useState(false)
  const menuScroll = useRef<HTMLDivElement>(null)
  const lastActivity = useRef(0)
  const guestInteracted = useRef(false)
  const submitLock = useRef(false)
  const checkoutAttempt = useRef<{ signature: string; id: string } | null>(null)
  const tableRequest = useRef(0)
  const voice = useKioskVoice((event) => {
    if (event.type === 'session' || event.type === 'ended') {
      clearGuestState()
      if (event.type === 'session' && event.session_token) {
        setToken(event.session_token)
        localDispatch({
          type: 'hydrate',
          state: {
            cart: event.cart || [],
            fulfillment: event.fulfillment || '',
            tableLabel: event.tableLabel || '',
            orderNote: ('orderNote' in event && event.orderNote) || '',
            quote: event.quote || null,
            revision: event.revision || 0,
          },
          newGuest: true,
        })
        setLoading(false)
      } else {
        setToken('')
        setLoading(true)
        setBootRevision((value) => value + 1)
      }
    } else if (event.type === 'state') {
      localDispatch({
        type: 'hydrate',
        state: {
          cart: event.cart || [],
          fulfillment: event.fulfillment || '',
          tableLabel: event.tableLabel || '',
          orderNote: ('orderNote' in event && event.orderNote) || '',
          quote: event.quote || null,
          revision: event.revision || 0,
        } as KioskState,
      })
    } else if (event.type === 'view') {
      if (event.view === 'menu') {
        setCategory('all')
        setQuery(event.query || '')
        setVoiceMenuIds(event.item_ids ?? null)
      }
      if (['menu', 'cart', 'payment', 'progress'].includes(event.view || '')) {
        showView(event.view as NavigationAction)
      }
    } else if (event.type === 'order' && event.order) {
      checkoutAttempt.current = null
      setSuccess(event.order)
    }
  }, token)
  function dispatch(action: Action) {
    if (submitLock.current) return
    if (action.type === 'table') tableRequest.current += 1
    if (
      voice.isActive() &&
      [
        'add',
        'quantity',
        'remove',
        'line_note',
        'order_note',
        'fulfillment',
        'table',
        'clear',
      ].includes(action.type)
    ) {
      void voice.action(action).catch((error) => setError(errorText(error)))
    } else localDispatch(action)
  }
  async function selectFulfillment(value: Fulfillment) {
    if (submitLock.current) return
    const request = ++tableRequest.current
    const captured = epoch.current
    const current = stateRef.current
    setError('')
    dispatch({ type: 'fulfillment', value })
    if (!merchantConnected || value !== 'at_table') return
    setTablesLoading(true)
    try {
      const live = await api.tables()
      if (captured !== epoch.current || request !== tableRequest.current) return
      setTables(live.tables)
      const currentTable = live.tables.find(
        (table) => table.available && table.name === current.tableLabel,
      )
      if (voice.isActive()) return
      if (!currentTable && live.first_available) {
        localDispatch({ type: 'table', value: live.first_available.name })
      } else if (!currentTable) {
        localDispatch({ type: 'table', value: '' })
        throw new ApiError('no_available_tables')
      }
    } catch (error) {
      if (captured === epoch.current && request === tableRequest.current) setError(errorText(error))
    } finally {
      if (captured === epoch.current && request === tableRequest.current) setTablesLoading(false)
    }
  }
  useEffect(() => {
    const captured = epoch.current
    let active = true
    void Promise.all([
      api.session(),
      api.menu(),
      fetch('/menu-images.json')
        .then((response) => (response.ok ? response.json() : {}))
        .catch(() => ({})),
    ])
      .then(([session, menu, imageMap]) => {
        if (active && captured === epoch.current) {
          setToken(session.session_token)
          setItems(menu.items)
          setCatalogs(menu.categories ?? [])
          setMerchantConnected(menu.merchant_connected)
          setImages(imageMap)
          lastActivity.current = Date.now()
          setLoading(false)
        }
      })
      .catch((error) => {
        if (active) {
          setBootError(errorText(error))
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [bootRevision])
  function clearGuestState() {
    epoch.current += 1
    setGeneration(epoch.current)
    setBootError('')
    localDispatch({ type: 'reset' })
    setSelected(null)
    navigate('reset')
    setSubmitting(false)
    submitLock.current = false
    checkoutAttempt.current = null
    setSuccess(null)
    setError('')
    setQuery('')
    setVoiceMenuIds(null)
    setCategory('all')
    setIdle(false)
    setShowScrollTop(false)
    menuScroll.current?.scrollTo({ top: 0, behavior: 'instant' })
    guestInteracted.current = false
    lastActivity.current = Date.now()
  }
  function resetGuest() {
    if (submitLock.current) return
    if (voice.isActive()) {
      voice.end()
      return
    }
    clearGuestState()
    setLoading(true)
    setToken('')
    setBootRevision((value) => value + 1)
  }
  // Staff-tuned idle time (Settings → Kiosk); read again for every new guest.
  const idleSeconds = useRef(DEFAULT_IDLE_SECONDS)
  useEffect(() => {
    let active = true
    api
      .kioskTiming()
      .then((timing) => {
        if (active) idleSeconds.current = timing.values.idle_seconds
      })
      .catch(() => {
        // Keep the previous value; the server still ends idle voice sessions itself.
      })
    return () => {
      active = false
    }
  }, [bootRevision])
  const idleActions = useRef({
    activity: voice.activity,
    active: voice.isActive,
    reset: resetGuest,
  })
  useLayoutEffect(() => {
    idleActions.current = { activity: voice.activity, active: voice.isActive, reset: resetGuest }
  })
  useEffect(() => {
    const activity = () => {
      guestInteracted.current = true
      lastActivity.current = Date.now()
      setIdle(false)
      idleActions.current.activity()
    }
    window.addEventListener('pointerdown', activity)
    window.addEventListener('keydown', activity)
    window.addEventListener('wheel', activity, { passive: true })
    const timer = window.setInterval(() => {
      if (
        !guestInteracted.current ||
        loading ||
        submitLock.current ||
        idleActions.current.active()
      ) {
        lastActivity.current = Date.now()
        return
      }
      const elapsed = Date.now() - lastActivity.current
      if (elapsed >= idleSeconds.current * 1000) idleActions.current.reset()
      else if (elapsed >= idleNoticeMs(idleSeconds.current)) setIdle(true)
    }, 1000)
    return () => {
      clearInterval(timer)
      window.removeEventListener('pointerdown', activity)
      window.removeEventListener('keydown', activity)
      window.removeEventListener('wheel', activity)
    }
  }, [loading])
  function add(
    item: MenuItem,
    quantity = 1,
    options: Options = Object.fromEntries(
      Object.entries(item.options).map(([key, values]) => [key, values[0]]),
    ),
  ) {
    const next = reducer(stateRef.current, { type: 'add', item, quantity, options })
    if (next === stateRef.current) {
      setError('Mỗi yêu cầu tối đa 20 dòng và 100 món. Bạn giảm số lượng nhé.')
      return
    }
    setError('')
    dispatch({ type: 'add', item, quantity, options })
  }
  async function checkout(snapshot = stateRef.current) {
    if (submitLock.current || !token || !snapshot.cart.length) return
    if (
      !snapshot.fulfillment ||
      (snapshot.fulfillment === 'at_table' && !snapshot.tableLabel.trim())
    ) {
      setError(
        snapshot.fulfillment === 'at_table'
          ? 'Bạn nhập số bàn để phục vụ đúng chỗ nhé.'
          : 'Bạn chọn dùng tại quán hoặc mang đi trước nhé.',
      )
      showView('cart')
      requestAnimationFrame(() =>
        document
          .getElementById(snapshot.fulfillment === 'at_table' ? 'table-label' : 'fulfillment')
          ?.focus(),
      )
      return
    }
    submitLock.current = true
    setSubmitting(true)
    setError('')
    const captured = epoch.current
    const payload = {
      lines: [...snapshot.cart]
        .sort((a, b) => a.key.localeCompare(b.key))
        .map((line) => ({
          item_id: line.item.id,
          quantity: line.quantity,
          options: Object.fromEntries(
            Object.entries(line.options).sort(([a], [b]) => a.localeCompare(b)),
          ),
          note: (line.note || '').trim(),
        })),
      fulfillment: snapshot.fulfillment,
      table_label: snapshot.fulfillment === 'at_table' ? snapshot.tableLabel.trim() : null,
      order_note: snapshot.orderNote.trim(),
    }
    const signature = JSON.stringify(payload)
    if (!checkoutAttempt.current || checkoutAttempt.current.signature !== signature) {
      checkoutAttempt.current = { signature, id: crypto.randomUUID() }
    }
    try {
      if (voice.isActive()) {
        await voice.command({ type: 'checkout' })
      } else {
        const order = await api.checkout(token, {
          checkout_id: checkoutAttempt.current.id,
          ...payload,
        })
        if (captured === epoch.current) {
          checkoutAttempt.current = null
          setSuccess(order)
          localDispatch({ type: 'clear' })
        }
      }
    } catch (error) {
      if (captured === epoch.current) {
        setError(errorText(error))
        if (
          error instanceof ApiError &&
          [
            'catalog_changed',
            'quote_expired',
            'stale_catalog',
            'sold_out',
            'invalid_options',
            'fulfillment_required',
            'table_required',
            'item_not_found',
            'invalid_lines',
            'invalid_quantity',
            'quantity_limit',
          ].includes(error.code)
        )
          checkoutAttempt.current = null
      }
    } finally {
      if (captured === epoch.current) {
        submitLock.current = false
        setSubmitting(false)
      }
    }
  }
  useEffect(() => {
    if (success) {
      navigate('payment')
      const panel = document.getElementById('checkout-panel')
      if (panel) panel.scrollTop = 0
    }
  }, [success])
  const menuResults = voiceMenuIds
    ? items.filter((item) => voiceMenuIds.includes(item.id))
    : filterMenu(items, query)
  const orderedCatalogs = useMemo(() => {
    const list = [...catalogs]
    // Swap 'món trà' and 'món ăn' if needed
    const teaIdx = list.findIndex((c) => c.name.trim().toLowerCase() === 'món trà')
    const foodIdx = list.findIndex((c) => c.name.trim().toLowerCase() === 'món ăn')
    if (teaIdx !== -1 && foodIdx !== -1 && teaIdx > foodIdx) {
      const temp = list[foodIdx]
      list[foodIdx] = list[teaIdx]
      list[teaIdx] = temp
    }

    // Move 'nước giải khát' replace 'món bánh'
    const drinkIdx = list.findIndex((c) => c.name.trim().toLowerCase() === 'nước giải khát')
    const cakeIdx = list.findIndex((c) => c.name.trim().toLowerCase() === 'món bánh')
    if (drinkIdx !== -1 && cakeIdx !== -1 && drinkIdx < cakeIdx) {
      const temp = list[drinkIdx]
      list[drinkIdx] = list[cakeIdx]
      list[cakeIdx] = temp
    }

    // Rule: categories with items come first; empty categories (0 items) must never be above non-empty categories
    const hasItems = (cat: MenuCategory) =>
      items.some(
        (item) =>
          item.category_id === cat.id ||
          item.category.trim().toLowerCase() === cat.name.trim().toLowerCase(),
      )

    const nonEmpty = list.filter((c) => hasItems(c))
    const empty = list.filter((c) => !hasItems(c))
    return [...nonEmpty, ...empty]
  }, [catalogs, items])
  const categories = [
    { key: 'all', label: t('Tất cả'), icon: allCategory },
    { key: '__top_sell__', label: t('Bán chạy'), icon: bestSellerCategory },
    { key: '__new_product__', label: t('Món mới'), icon: newCategory },
    ...orderedCatalogs.map(({ id, name }) => ({
      key: id,
      label: name.charAt(0).toLocaleUpperCase('vi') + name.slice(1),
      icon: categoryIcons[name.trim().toLocaleLowerCase('vi')] || allCategory,
    })),
  ]
  const visible = menuResults.filter((item) => {
    if (category === 'all') return true
    if (category === '__top_sell__') return item.is_top_sell === true
    if (category === '__new_product__') return item.is_new === true
    return (item.category_id || item.category.trim()) === category
  })
  const cart = (
    <Cart
      key={generation}
      state={state}
      dispatch={dispatch}
      images={images}
      submitting={submitting}
      onFulfillment={selectFulfillment}
      tables={tables}
      tablesLoading={tablesLoading}
      merchantConnected={merchantConnected}
    />
  )
  const cartCount = state.cart.reduce((count, line) => count + line.quantity, 0)
  const cartTotal = state.cart.reduce(
    (total, line) => total + line.quantity * line.item.price_vnd,
    0,
  )
  const viewingResult = !cartCount && Boolean(success)
  const showPayment = viewingResult && Boolean(success?.merchant)
  const assistantIdle = voice.enabled && voice.armed && !voice.active
  if ((loading || bootError) && !assistantIdle)
    return (
      <main className="boot-screen">
        <img src={halloweenLogo} alt="Trend Coffee" className="boot-brand-logo" draggable={false} />
        <h1>{loading ? t('Trend đang chuẩn bị thực đơn…') : t('Chưa kết nối được với Trend')}</h1>
        <p>{t(bootError) || t('Một chút cà phê, một ngày thật vui.')}</p>
        {bootError && (
          <Button className="primary-action" onClick={resetGuest}>
            {t('Thử kết nối lại')}
          </Button>
        )}
      </main>
    )
  return (
    <div
      className={
        'simple-kiosk' +
        (voice.enabled ? ' avatar-kiosk' : '') +
        (assistantIdle ? ' assistant-idle' : '') +
        (success ? ' checkout-open' : '') +
        (navigation.open ? ' sidebar-open' : ' sidebar-closed')
      }
      data-character={character}
    >
      {!assistantIdle && (
        <header className="topbar">
          <a
            href="/"
            className="brand brand-halloween"
            aria-label={t('Trend Coffee, trang thực đơn')}
            onClick={(event) => {
              event.preventDefault()
              showView('menu')
              setCategory('all')
              setQuery('')
              setVoiceMenuIds(null)
            }}
          >
            <img
              src={halloweenLogo}
              alt="Trend Coffee"
              className="brand-logo-img"
              draggable={false}
            />
          </a>
          <div className="header-actions">
            {settingsVisible && <SettingsDialog voice={voice} />}
            <Button
              variant="ghost"
              className="navigation-toggle header-cart"
              size="icon"
              aria-label={t('Xem giỏ hàng')}
              aria-controls="checkout-panel"
              onClick={() => showView('cart')}
            >
              <span className="checkout-dock-bag cart-bucket">
                <img src={cartBucket} alt="" draggable={false} />
                <span className="checkout-dock-count">{cartCount}</span>
              </span>
            </Button>
            <Button
              ref={navigationButton}
              variant="ghost"
              className="navigation-toggle"
              size="icon"
              aria-label={t('Mở hoặc đóng thanh bên')}
              aria-controls="checkout-panel"
              aria-expanded={navigation.open}
              onClick={() => navigate('toggle')}
            >
              <Menu />
            </Button>
          </div>
        </header>
      )}
      {idle && !assistantIdle && (
        <div className="idle-notice" role="status">
          {t('Phiên sẽ kết thúc sau 30 giây không tương tác.')}
          <Button
            variant="ghost"
            onClick={() => {
              setIdle(false)
              lastActivity.current = Date.now()
            }}
          >
            {t('Tiếp tục chọn món')}
          </Button>
        </div>
      )}
      <div className="kiosk-layout">
        {voice.enabled && <AvatarAssistant voice={voice} token={token} />}
        <div
          className="menu-workspace"
          hidden={assistantIdle}
          ref={menuScroll}
          onScroll={(event) => setShowScrollTop(event.currentTarget.scrollTop > 200)}
        >
          <nav className="category-rail" aria-label={t('Danh mục thực đơn')}>
            <div className="category-list">
              {categories.map(({ key, label, icon }) => (
                <button
                  key={key}
                  className={'category-button ' + (category === key ? 'active' : '')}
                  aria-pressed={category === key}
                  onClick={() => {
                    setCategory(key)
                    setQuery('')
                    setVoiceMenuIds(null)
                  }}
                >
                  <span className="category-icon">
                    <img src={icon} alt="" draggable={false} />
                  </span>
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </nav>
          <main className="menu-main">
            <section aria-labelledby="menu-heading" className="menu-section">
              <div className="menu-toolbar">
                <div>
                  <h2 id="menu-heading">
                    {category === 'all'
                      ? t('Thực đơn')
                      : categories.find((item) => item.key === category)?.label}
                  </h2>
                </div>
                <div className="search-control">
                  <Search />
                  <label htmlFor="menu-search" className="sr-only">
                    {t('Tìm món')}
                  </label>
                  <Input
                    id="menu-search"
                    placeholder={t('Tìm món…')}
                    value={query}
                    autoComplete="off"
                    autoCorrect="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    onChange={(event) => {
                      setQuery(event.target.value)
                      setVoiceMenuIds(null)
                    }}
                  />
                  {query && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="search-clear-btn"
                      aria-label={t('Xóa tìm kiếm')}
                      onClick={() => {
                        setQuery('')
                        setVoiceMenuIds(null)
                      }}
                    >
                      <X />
                    </Button>
                  )}
                </div>
              </div>
              {error && !navigation.open && (
                <div className="global-error no-results-banner" role="alert">
                  <div className="global-error-body">
                    <AlertCircle className="no-results-icon" aria-hidden="true" />
                    <span className="no-results-title">{t(error)}</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={t('Đóng thông báo')}
                    onClick={() => setError('')}
                  >
                    <X />
                  </Button>
                </div>
              )}
              {selected && !assistantIdle && (
                <ProductPanel
                  key={selected.id}
                  item={selected}
                  locked={submitting}
                  images={images}
                  onClose={() => setSelected(null)}
                  onAdd={add}
                />
              )}
              {visible.length === 0 ? (
                <div className="no-results" role="status">
                  <div className="no-results-banner">
                    <AlertCircle className="no-results-icon" aria-hidden="true" />
                    <span className="no-results-title">{t('Chưa tìm thấy món này')}</span>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="no-results-btn"
                    onClick={() => {
                      setQuery('')
                      setVoiceMenuIds(null)
                      setCategory('all')
                    }}
                  >
                    {t('Xem tất cả món')}
                  </Button>
                </div>
              ) : (
                <div className="product-grid">
                  {visible.map((item, index) => (
                    <article
                      className={
                        'product-card' +
                        (item.stale || item.availability === 'sold_out' ? ' is-unavailable' : '')
                      }
                      key={item.id}
                      onClick={() => {
                        if (!item.stale && item.availability !== 'sold_out') {
                          setSelected(item)
                        }
                      }}
                    >
                      <button
                        type="button"
                        className="product-photo"
                        aria-label={t('Xem') + ' ' + item.name}
                        disabled={submitting}
                        onClick={(event) => {
                          event.stopPropagation()
                          setSelected(item)
                        }}
                      >
                        <ProductImage item={item} images={images} eager={index < 3} />
                      </button>
                      <div className="product-card-body">
                        <button
                          type="button"
                          className="product-name"
                          onClick={(event) => {
                            event.stopPropagation()
                            setSelected(item)
                          }}
                        >
                          {item.name}
                        </button>
                        {item.variant_name && item.variant_name !== 'tiêu chuẩn' && (
                          <p className="product-variant">{item.variant_name}</p>
                        )}
                        <div className="product-price">
                          <strong>{money(item.price_vnd)}</strong>
                        </div>
                        {(item.stale || item.availability === 'sold_out') && (
                          <small className="unavailable">
                            {item.stale ? t('Cần cập nhật thực đơn') : t('Tạm hết món')}
                          </small>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </main>
        </div>
        {navigation.open && !assistantIdle && (
          <button
            className="sidebar-backdrop"
            aria-label={t('Đóng thanh bên')}
            onClick={closeSidebar}
          />
        )}
        {navigation.open && !assistantIdle && (
          <div
            className="sidebar-resize"
            style={{ right: `min(${sidebarWidth}px, 94vw)` }}
            role="separator"
            aria-label={t('Thay đổi độ rộng thanh bên')}
            aria-orientation="vertical"
            aria-valuemin={280}
            aria-valuemax={Math.max(280, Math.floor(window.innerWidth * 0.94))}
            aria-valuenow={Math.min(sidebarWidth, Math.floor(window.innerWidth * 0.94))}
            tabIndex={0}
            onPointerDown={(event) => {
              event.currentTarget.setPointerCapture(event.pointerId)
              event.preventDefault()
            }}
            onPointerMove={(event) => {
              if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                setSidebarWidth(
                  Math.max(
                    280,
                    Math.min(window.innerWidth * 0.94, window.innerWidth - event.clientX),
                  ),
                )
              }
            }}
            onKeyDown={(event) => {
              if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
                event.preventDefault()
                setSidebarWidth((width) =>
                  Math.max(
                    280,
                    Math.min(
                      window.innerWidth * 0.94,
                      width + (event.key === 'ArrowLeft' ? 20 : -20),
                    ),
                  ),
                )
              }
            }}
          />
        )}
        <aside
          ref={sidebar}
          tabIndex={-1}
          id="checkout-panel"
          className="cart-sidebar navigation-sidebar"
          style={{ width: `min(${sidebarWidth}px, 94vw)` }}
          aria-label={t('Giỏ hàng và thanh toán')}
          hidden={assistantIdle || !navigation.open}
        >
          <header className="sidebar-heading">
            <Button
              variant="ghost"
              size="icon"
              className="navigation-toggle"
              aria-label={t('Đóng thanh bên')}
              onClick={closeSidebar}
            >
              <X />
            </Button>
          </header>
          <nav className="sidebar-navigation" aria-label={t('Điều hướng kiosk')}>
            {(
              [
                ['cart', 'Giỏ hàng', ShoppingCart],
                ['payment', 'Thanh toán / QR', QrCode],
                ['progress', 'Đơn đã đặt', ClipboardList],
              ] as const
            ).map(([view, label, Icon]) => (
              <Button
                key={view}
                variant="ghost"
                className="sidebar-step"
                aria-pressed={navigation.view === view}
                onClick={() => showView(view)}
              >
                <span className="sidebar-step-icon">
                  <Icon aria-hidden="true" />
                </span>
                <span className="sidebar-step-label">
                  {view === 'payment' && language === 'vi' ? 'Thanh toán' : t(label)}
                </span>
              </Button>
            ))}
          </nav>
          {error && (
            <div className="global-error no-results-banner" role="alert">
              <div className="global-error-body">
                <AlertCircle className="no-results-icon" aria-hidden="true" />
                <span className="no-results-title">{t(error)}</span>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t('Đóng thông báo')}
                onClick={() => setError('')}
              >
                <X />
              </Button>
            </div>
          )}
          {navigation.view === 'cart' && cart}
          {navigation.view === 'payment' &&
            (success ? (
              <CheckoutResult
                order={success}
                token={token}
                onProgress={() => showView('progress')}
              />
            ) : (
              token && <PaymentQr key={token} token={token} />
            ))}
          <ProgressPanel
            key={'progress-' + generation}
            open={progress}
            token={token}
            images={images}
          />
        </aside>
      </div>
      {!assistantIdle && (
        <nav className="checkout-dock" aria-label={t('Giỏ hàng và thanh toán')}>
          <div className="dock-order-preview">
            <button
              type="button"
              className="checkout-dock-summary"
              aria-label={t('Xem giỏ hàng')}
              onClick={() => showView('cart')}
            >
              <span className="checkout-dock-bag cart-bucket">
                <img src={cartBucket} alt="" draggable={false} />
                <span className="checkout-dock-count">{cartCount}</span>
              </span>
            </button>
            <div className="dock-products" aria-label={t('Món trong giỏ hàng')}>
              {state.cart.length === 0 ? (
                <span className="dock-empty">{t('Chưa có món trong giỏ.')}</span>
              ) : (
                state.cart.map((line) => (
                  <div className="dock-product" key={line.key}>
                    <button
                      type="button"
                      className="dock-product-view"
                      onClick={() => showView('cart')}
                      aria-label={t('Xem') + ' ' + line.item.name}
                    >
                      <span className="dock-product-image">
                        <ProductImage item={line.item} images={images} />
                      </span>
                      <span className="dock-product-quantity" aria-hidden="true">
                        {line.quantity}
                      </span>
                      <span className="sr-only">
                        {line.item.name} {line.quantity} × {money(line.item.price_vnd)}
                      </span>
                    </button>
                    <button
                      type="button"
                      className="dock-product-remove"
                      disabled={submitting}
                      aria-label={t('Bỏ món') + ' ' + line.item.name}
                      onClick={() => dispatch({ type: 'remove', key: line.key })}
                    >
                      <span aria-hidden="true">×</span>
                    </button>
                  </div>
                ))
              )}
            </div>
            <div className="dock-total">
              <span>{t('Tạm tính')}</span>
              <strong>{money(cartTotal)}</strong>
            </div>
          </div>
          <div className="dock-controls">
            {!success && (
              <Button
                type="button"
                variant="outline"
                className="checkout-dock-cancel"
                disabled={submitting}
                onClick={resetGuest}
              >
                {t('Hủy')}
              </Button>
            )}
            <Button
              type="button"
              className="checkout-dock-action"
              aria-label={!viewingResult ? t('Thanh toán') : undefined}
              disabled={submitting || (!cartCount && !success)}
              onClick={() => {
                if (viewingResult) {
                  showView(showPayment ? 'payment' : 'progress')
                } else {
                  void checkout()
                }
              }}
            >
              {showPayment
                ? t('Xem thanh toán')
                : viewingResult
                  ? t('Xem tiến độ yêu cầu')
                  : t('Đến thanh toán')}
            </Button>
          </div>
        </nav>
      )}
      {showScrollTop && !assistantIdle && !navigation.open && (
        <button
          type="button"
          className="scroll-top"
          aria-label={t('Cuộn lên đầu trang')}
          onClick={() =>
            menuScroll.current?.scrollTo({
              top: 0,
              behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
                ? 'instant'
                : 'smooth',
            })
          }
        >
          <ChevronUp aria-hidden="true" />
        </button>
      )}
      {keyboardEnabled && <VirtualKeyboard />}
    </div>
  )
}
