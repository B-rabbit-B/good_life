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
      // common：对话页与其他页面共用的几个小模块（日期、标签、动效偏好、后端文案副本、仅供参考、敏感区、按钮式链接、
      // 图标按钮、页头、需要授权、模型服务的钩子；对话页的待处理条与医嘱页共用的医嘱钩子、到期原因、提出人，以及两边都用的折叠与医嘱条目样式）放进同一块。
      // 不这样设时，每多一个按需加载的页面用到它们，Rolldown 就按“谁在用”把它们切成更多的小块，对话页首屏要多请求、
      // 多付每块的压缩开销（只有医嘱页用的钩子在 api/hooks/medicalPage.ts，不在这一块）
      rolldownOptions: {
        output: {
          codeSplitting: {
            groups: [
              { name: 'initial', tags: ['$initial'] },
              {
                name: 'common',
                minShareCount: 2,
                test: /[\\/]src[\\/](lib[\\/](dates|labels|motion|contract)|components[\\/](RefTag|Sensitive|ButtonLink|IconButton|PageHeader|states[\\/]AuthNeededState)|api[\\/]hooks[\\/](llm|medical)\.|features[\\/]medical[\\/](dueReason|proposer|useItemContext)\.|styles[\\/]components[\\/](fold|medical-item)\.css)/,
              },
            ],
          },
        },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      css: false,
    },
  }
})
