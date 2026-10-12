import '../../styles/components/chat.css'

/** 用户气泡：钴蓝，起点一角 8 在右下 */
export function UserMessage({ text }: { text: string }) {
  return <div className="msg-u"><span>{text}</span></div>
}
