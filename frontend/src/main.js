import { createApp } from 'vue'
// WebSocket scheme guard: normalize accidental 'wsss://' to 'wss://'
if (typeof window !== 'undefined' && typeof window.WebSocket !== 'undefined') {
  const OriginalWebSocket = window.WebSocket
  window.WebSocket = function (url, protocols) {
    try {
      if (typeof url === 'string' && url.startsWith('wsss://')) {
        url = 'wss://' + url.slice('wsss://'.length)
      }
    } catch (_) {}
    return new OriginalWebSocket(url, protocols)
  }
  window.WebSocket.prototype = OriginalWebSocket.prototype
  window.WebSocket.OPEN = OriginalWebSocket.OPEN
  window.WebSocket.CONNECTING = OriginalWebSocket.CONNECTING
  window.WebSocket.CLOSING = OriginalWebSocket.CLOSING
  window.WebSocket.CLOSED = OriginalWebSocket.CLOSED
}
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
