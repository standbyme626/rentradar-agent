import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './assets/main.css'

createApp(App).use(createPinia()).use(router).mount('#app')

window.addEventListener('rentradar:unauthorized', () => {
  const auth = useAuthStore()
  auth.clear()
  const current = router.currentRoute.value
  if (current.name !== 'login') {
    void router.push({ name: 'login', query: { redirect: current.fullPath } })
  }
})
