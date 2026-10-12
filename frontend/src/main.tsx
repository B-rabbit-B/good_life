// 占位入口：任务 4 换成真正的应用（路由、守卫与外壳）；样张页那时改为一条路由
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { CoverProvider } from './components/cover'
import { Field } from './components/Field'
import { GlassModeProvider } from './components/glass/GlassModeProvider'
import { ToastProvider } from './components/Toast'
import './styles/fonts.css'
import './styles/tokens.css'
import './styles/base.css'
import './styles/materials.css'

const container = document.getElementById('root')
if (!container) throw new Error('index.html 里缺少 #root')
const root = createRoot(container)

// 组件样张页只在开发模式或 VITE_GALLERY=1（端到端构建）时提供，按需加载，不进正式包的首屏
const galleryEnabled = import.meta.env.DEV || import.meta.env.VITE_GALLERY === '1'

if (galleryEnabled && window.location.pathname === '/dev/gallery') {
  void import('./dev/GalleryPage').then(({ GalleryPage }) => {
    root.render(
      <StrictMode>
        <GlassModeProvider>
          <CoverProvider>
            <ToastProvider>
              <BrowserRouter>
                <GalleryPage />
              </BrowserRouter>
            </ToastProvider>
          </CoverProvider>
        </GlassModeProvider>
      </StrictMode>,
    )
  })
} else {
  root.render(
    <StrictMode>
      <Field />
      <main>good-life</main>
    </StrictMode>,
  )
}
