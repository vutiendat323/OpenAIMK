import { rm } from 'node:fs/promises'
// Never empty the static root: staff console files share it with the kiosk.
await rm(new URL('../../trendcoffee/static/kiosk-assets', import.meta.url), {
  recursive: true,
  force: true,
})
