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
      // 入口静态引入的模块全部留在入口块里。不这样设时，按需加载的页面一用到 React Aria 的输入框、数字框或分段，
      // Rolldown 就把它们与入口共用的模块拆成几个公共块，入口要多请求几个文件、分开压缩，首屏脚本多出约 3 KB
      rolldownOptions: { output: { codeSplitting: { groups: [{ name: 'initial', tags: ['$initial'] }] } } },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      css: false,
    },
  }
})
