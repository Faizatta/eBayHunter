import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'   // ✅ ADD THIS

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),  // ✅ ADD THIS
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:5000',
        changeOrigin: true,
      }
    }
  }
})
