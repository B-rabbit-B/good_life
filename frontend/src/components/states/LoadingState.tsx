import '../../styles/components/states.css'

const width = (w: string) => ({ width: w })

/** 加载：骨架块（圆角浅青条加扫光，减弱动效时不扫光）与一行 role="status" 文字。diary 是饮食记录，list 是列表，page 是一般页面。 */
export function LoadingState({ variant, text }: { variant: 'diary' | 'list' | 'page'; text: string }) {
  return (
    <div className="ld" aria-busy="true">
      {variant === 'diary' && (
        <>
          <div className="plate" aria-hidden="true">
            <div className="sk" style={{ width: '46%', height: 36 }} />
            <div className="sk" style={{ height: 30, marginTop: 16 }} />
            <div className="ld-row"><div className="sk" /><div className="sk" /><div className="sk" /><div className="sk" /></div>
          </div>
          <div className="plate" aria-hidden="true">
            <div className="sk" style={width('80%')} />
            <div className="sk" style={width('64%')} />
            <div className="sk" style={width('72%')} />
          </div>
        </>
      )}
      {variant === 'list' && (
        <div className="plate" aria-hidden="true">
          {['78%', '56%', '84%', '62%', '70%'].map((w) => <div key={w} className="sk" style={width(w)} />)}
        </div>
      )}
      {variant === 'page' && (
        <div className="pad" aria-hidden="true">
          <div className="sk" style={{ width: '42%', height: 28, marginTop: 8 }} />
          <div className="sk" style={{ width: '90%', marginTop: 20 }} />
          <div className="sk" style={width('76%')} />
          <div className="sk" style={width('84%')} />
        </div>
      )}
      <p className="t-cap ld-text" role="status">{text}</p>
    </div>
  )
}
