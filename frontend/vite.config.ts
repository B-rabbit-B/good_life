import basicSsl from '@vitejs/plugin-basic-ssl'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// 一轮对话可能连续调用模型很久才开始推送，所以代理的超时放宽到 5 分钟
const API_TIMEOUT_MS = 300_000

export default defineConfig(({ mode }) => {
  const lan = mode === 'lan'
  return {
    plugins: lan ? [react(), basicSsl()] : [react()],
    server: {
      port: 5173,
      strictPort: true,
      ...(lan ? { host: '0.0.0.0' } : {}),
      proxy: {
        '/api': { target: 'http://127.0.0.1:8000', timeout: API_TIMEOUT_MS, proxyTimeout: API_TIMEOUT_MS },
      },
    },
    build: {
      target: ['safari16', 'chrome107'],
      manifest: true,
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      css: false,
    },
  }
})
