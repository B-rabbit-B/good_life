/** 背景场：应用根节点的静态背景（--field 渐变加颗粒），固定在视口上，不随路由重绘。 */
export function Field() {
  return <div className="field" aria-hidden="true" />
}
