// 占位入口：任务 4 换成真正的应用（路由、守卫与外壳）
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/fonts.css'

const container = document.getElementById('root')
if (!container) throw new Error('index.html 里缺少 #root')

createRoot(container).render(
  <StrictMode>
    <main>good-life</main>
  </StrictMode>,
)
