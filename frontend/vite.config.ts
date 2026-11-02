import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://192.168.31.197:8010',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://192.168.31.197:8010',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://192.168.31.197:8010',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
