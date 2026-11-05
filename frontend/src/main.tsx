import { setNonce } from 'get-nonce'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { PreferencesProvider } from './preferences'

const nonce = document.querySelector<HTMLMetaElement>('meta[name="csp-nonce"]')?.content
if (nonce && nonce !== '__CSP_NONCE__') setNonce(nonce)

createRoot(document.getElementById('root')!).render(
  <PreferencesProvider>
    <App />
  </PreferencesProvider>,
)
