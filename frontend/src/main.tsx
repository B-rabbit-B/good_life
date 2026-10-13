// 全局样式先于组件引入：组件自己的样式表排在令牌、基础与材质之后
import './styles/fonts.css'
import './styles/tokens.css'
import './styles/base.css'
import './styles/materials.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './app/App'

const container = document.getElementById('root')
if (!container) throw new Error('index.html 里缺少 #root')

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
