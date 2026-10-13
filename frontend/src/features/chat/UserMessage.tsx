import { memo } from 'react'
import '../../styles/components/chat.css'

/** 用户气泡：钴蓝，起点一角 8 在右下（memo：流式回答每一帧重绘列表时，已有的气泡不跟着重绘） */
export const UserMessage = memo(function UserMessage({ text }: { text: string }) {
  return <div className="msg-u"><span>{text}</span></div>
})
