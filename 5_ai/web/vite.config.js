import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 28173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:28000',
        changeOrigin: true,
      },
    },
  },
})
