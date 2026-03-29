import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function renderStartupError(error, context = 'startup') {
  const root = document.getElementById('app') || document.body
  const message = error?.stack || error?.message || String(error)
  root.innerHTML = `
    <div style="min-height:100vh;background:#0d0d0d;color:#e8e8e8;padding:32px;font-family:JetBrains Mono,monospace;">
      <h1 style="font-size:18px;margin:0 0 16px;color:#ff5722;">MiroFish failed to start</h1>
      <p style="margin:0 0 12px;color:#aaa;">Context: ${escapeHtml(context)}</p>
      <pre style="white-space:pre-wrap;word-break:break-word;background:#161616;border:1px solid #252525;padding:16px;border-radius:8px;">${escapeHtml(message)}</pre>
    </div>
  `
}

window.addEventListener('error', (event) => {
  renderStartupError(event.error || event.message, 'window.error')
})

window.addEventListener('unhandledrejection', (event) => {
  renderStartupError(event.reason || 'Unhandled promise rejection', 'unhandledrejection')
})

try {
  const app = createApp(App)

  app.config.errorHandler = (error, instance, info) => {
    console.error('Vue startup error:', error, info, instance)
    renderStartupError(error, `vue:${info}`)
  }

  app.use(router)
  app.mount('#app')
} catch (error) {
  console.error('Bootstrap failure:', error)
  renderStartupError(error, 'bootstrap')
}
