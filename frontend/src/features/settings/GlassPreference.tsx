import { useGlassPreference, type ReduceTransparencyPref } from '../../components/glass/GlassModeProvider'
import { RadioSegment } from '../../components/RadioSegment'

const OPTIONS: { value: ReduceTransparencyPref; label: string }[] = [
  { value: 'system', label: '跟随系统' }, { value: 'on', label: '开' }, { value: 'off', label: '关' },
]

/** “减少透明”：跟随系统 / 开 / 关（存在本机，永远优先于系统偏好与低端机判定）。 */
export function GlassPreference() {
  const [pref, setPref] = useGlassPreference()
  return (
    <RadioSegment
      label="减少透明" value={pref} options={OPTIONS} hint="会关掉磨砂玻璃，界面改用实色，更省电。"
      onChange={(value) => setPref(value as ReduceTransparencyPref)}
    />
  )
}
