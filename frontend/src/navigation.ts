export type SidebarView = 'cart' | 'payment' | 'progress'
export type NavigationAction = SidebarView | 'menu' | 'toggle' | 'close' | 'reset'
export type NavigationState = { open: boolean; view: SidebarView }
export const initialNavigation: NavigationState = { open: false, view: 'cart' }
export function navigationReducer(
  state: NavigationState,
  action: NavigationAction,
): NavigationState {
  if (action === 'reset') return initialNavigation
  if (action === 'menu' || action === 'close') return { ...state, open: false }
  if (action === 'toggle') return { ...state, open: !state.open }
  return { open: true, view: action }
}
