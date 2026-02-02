import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: '/organisation/',
  plugins: [vue()],
  optimizeDeps: {
    include: ['sql.js'],
  },
  server: {
    fs: {
      allow: ['.', '..'],
    },
  },
})
