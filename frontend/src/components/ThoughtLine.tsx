import '../styles/components/states.css'

/** 等待中的一行字：末尾钴蓝光标闪烁（减弱动效时不闪）；不加闪光或呼吸效果。 */
export function ThoughtLine({ text }: { text: string }) {
  return (
    <p className="thought" role="status">
      {text}
      <span className="caret" aria-hidden="true" />
    </p>
  )
}
