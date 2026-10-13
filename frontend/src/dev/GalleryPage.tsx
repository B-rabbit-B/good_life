// 组件样张页：/dev/gallery（开发模式或 VITE_GALLERY=1）。按设计稿“设计系统”一节与 12 块状态面板的顺序摆出全部共用组件，
// 供与 docs/superpowers/design/step11/index.html 并排比较。只做展示，数据都是设计稿里的示例。
import { useEffect, useState, type CSSProperties } from 'react'
import { ApiError } from '../api/errors'
import { BottomNav, type NavItem } from '../components/BottomNav'
import { Button } from '../components/Button'
import { ButtonLink } from '../components/ButtonLink'
import { CareBlock } from '../components/CareBlock'
import { Checkbox } from '../components/Checkbox'
import { ConfidenceCells } from '../components/ConfidenceCells'
import { ConfirmSheet } from '../components/ConfirmSheet'
import { CountUp } from '../components/CountUp'
import { CoverButton } from '../components/CoverButton'
import { useCover } from '../components/cover'
import { CycleTicks } from '../components/CycleTicks'
import { DateField } from '../components/DateField'
import { Dock } from '../components/Dock'
import { EvidenceFold } from '../components/EvidenceFold'
import { Field } from '../components/Field'
import { useGlassPreference, type ReduceTransparencyPref } from '../components/glass/GlassModeProvider'
import { Icon, type IconName } from '../components/Icon'
import { IconButton } from '../components/IconButton'
import { JumpCard } from '../components/JumpCard'
import { LedgerTicks } from '../components/LedgerTicks'
import { PageHeader } from '../components/PageHeader'
import { PasswordField } from '../components/PasswordField'
import { RadioSegment } from '../components/RadioSegment'
import { RefTag } from '../components/RefTag'
import { Ruler } from '../components/Ruler'
import { SegmentedTabs } from '../components/SegmentedTabs'
import { SelectField } from '../components/SelectField'
import { Sensitive } from '../components/Sensitive'
import { ShellPortal } from '../components/ShellPortal'
import { Sheet } from '../components/Sheet'
import { AuthNeededState } from '../components/states/AuthNeededState'
import { EmptyState } from '../components/states/EmptyState'
import { ErrorState } from '../components/states/ErrorState'
import { InsufficientState } from '../components/states/InsufficientState'
import { LoadingState } from '../components/states/LoadingState'
import { StatusMark } from '../components/StatusMark'
import { Surface } from '../components/Surface'
import { Switch } from '../components/Switch'
import { SystemSlip } from '../components/SystemSlip'
import { TagField } from '../components/TagField'
import { TextField } from '../components/TextField'
import { TextTabs } from '../components/TextTabs'
import { ThoughtLine } from '../components/ThoughtLine'
import { useToast } from '../components/Toast'
import { Title } from '../components/Title'
import { VerdictMark } from '../components/VerdictMark'
import { WillList } from '../components/WillList'
import '../styles/components/button.css'
import '../styles/components/field-input.css'
import '../styles/components/status-mark.css'
import './gallery.css'

const GALLERY = '/dev/gallery'
// 固定在屏幕底部的导航：样张页借“健康”一项当当前页
const SHELL_NAV: NavItem[] = [
  { key: 'chat', label: '对话', to: '/' },
  { key: 'records', label: '记录', to: '/records' },
  { key: 'health', label: '健康', to: GALLERY },
  { key: 'me', label: '我的', to: '/me' },
]
const NAV_THREE: NavItem[] = [
  { key: 'chat', label: '对话', to: '/' },
  { key: 'records', label: '记录', to: GALLERY },
  { key: 'me', label: '我的', to: '/me' },
]

const SWATCHES: [string, string, string][] = [
  ['linear-gradient(180deg,#F7FAFE,#E1EAF7)', '背景场', '#F7FAFE 到 #E1EAF7'],
  ['#fff', '瓷白', '#FFFFFF 面板'],
  ['var(--plate-2)', '瓷灰', '#F3F6FB 填充区'],
  ['var(--chrome-solid)', '釉（实色）', '#EAF1FA 玻璃降级'],
  ['var(--ink)', '海军蓝', '#0E1B33 正文 17.2:1'],
  ['var(--ink-2)', '蓝灰', '#33435E 次要 10.0:1'],
  ['var(--ink-3)', '淡蓝灰', '#4E5D76 说明 6.7:1'],
  ['var(--ink-4)', '刻度灰', '#8C9BB3 只画刻度'],
  ['var(--accent)', '钴蓝', '#1F58A8 强调 7.0:1'],
  ['var(--sky)', '天青', '#4F7FC2 只做图形'],
  ['var(--accent-wash)', '青浅底', '#E8F0FA'],
  ['var(--line-2)', '细线', '#E3E9F2，控件边 #C9D4E3'],
  ['var(--ok)', '松', '#1E6B4C 适合 6.4:1'],
  ['var(--warn-line)', '赭', '字 #8A5300 6.3:1，线 #B07A1E'],
  ['var(--danger)', '朱', '#B3261E 不建议与就医 6.5:1'],
  ['var(--scrim)', '遮罩', '海军蓝 38%，不模糊'],
]

const ICONS: [IconName, string][] = [
  ['camera', '拍照'], ['image', '相册'], ['send', '发送'], ['cover', '遮盖'], ['pin', '地点'], ['nav', '导航'],
  ['alert', '警示'], ['info', '说明'], ['doc', '医嘱'], ['lock', '掩码'], ['refresh', '重试'], ['phone', '拨打'],
  ['search', '搜索'], ['cal', '日期'], ['clock', '时间'], ['edit', '修改'], ['trash', '删除'], ['bowl', '一餐'],
  ['back', '返回'], ['down', '展开'], ['right', '进入'], ['eye', '显示'], ['plus', '添加'], ['check', '完成'], ['x', '移除'],
]

const PROOF: { tier: 'chrome' | 'sheet' | 'still'; bg: string; title: string; lines: [string, string, string, string]; r: string }[] = [
  { tier: 'chrome', bg: '#FFFFFF', title: '活玻璃 · 白底', lines: ['c1', '正文 海军蓝', 'c2', '导航 蓝灰'], r: '14.2 / 8.3' },
  { tier: 'chrome', bg: '#B3C7E5', title: '活玻璃 · 背景场最深处', lines: ['c1', '正文 海军蓝', 'c2', '导航 蓝灰'], r: '12.3 / 7.2' },
  { tier: 'chrome', bg: 'var(--accent)', title: '活玻璃 · 钴蓝气泡与按钮', lines: ['c1', '正文 海军蓝', 'c2', '导航 蓝灰'], r: '9.1 / 5.3' },
  { tier: 'chrome', bg: 'var(--danger)', title: '活玻璃 · 就医朱色块', lines: ['c1', '正文 海军蓝', 'c2', '导航 蓝灰'], r: '8.7 / 5.1' },
  { tier: 'chrome', bg: 'var(--ink)', title: '活玻璃 · 海军蓝（参考，不计入）', lines: ['c1', '正文 海军蓝', 'c2', '导航 蓝灰'], r: '7.6 / 4.4' },
  { tier: 'sheet', bg: '#FFFFFF', title: '厚玻璃 · 白底', lines: ['c3', '说明 淡蓝灰', 'danger', '不能撤销 朱'], r: '6.4 / 6.3' },
  { tier: 'sheet', bg: '#0C1930', title: '厚玻璃 · 遮罩下的海军蓝', lines: ['c3', '说明 淡蓝灰', 'danger', '不能撤销 朱'], r: '5.0 / 4.9' },
  { tier: 'sheet', bg: '#173F79', title: '厚玻璃 · 遮罩下的钴蓝', lines: ['c3', '说明 淡蓝灰', 'danger', '不能撤销 朱'], r: '5.2 / 5.1' },
  { tier: 'sheet', bg: '#732023', title: '厚玻璃 · 遮罩下的朱色', lines: ['c3', '说明 淡蓝灰', 'warn', '待复核 赭'], r: '5.1 / 4.9' },
  { tier: 'still', bg: '#F7FAFE', title: '静玻璃 · 背景场最亮处', lines: ['c3', '今天想问你 淡蓝灰', 'danger', '医嘱提醒 朱'], r: '6.5 / 6.4' },
  { tier: 'still', bg: '#B3C7E5', title: '静玻璃 · 背景场最深处', lines: ['c3', '今天想问你 淡蓝灰', 'danger', '医嘱提醒 朱'], r: '5.6 / 5.5' },
]
const LINE_COLOR: Record<string, CSSProperties | undefined> = {
  danger: { color: 'var(--danger)' },
  warn: { color: 'var(--warn)' },
}

const MOTION: [string, string, string, string, 'count' | 'ledger' | 'sheet' | null][] = [
  ['回答流入', '按服务端分段逐字显示，钴蓝光标', '跟随数据', '整段一次出现', null],
  ['数字变化', '从旧值数到新值', '600 ms，缓出', '直接显示终值', 'count'],
  ['能量刻度', '刻度从左到右依次长出', '480 ms，每格错开 6 ms', '直接显示', 'ledger'],
  ['底部面板', '以实色自下滑入，遮罩淡入；停稳后磨砂淡入', '320 ms，(.32,.72,0,1)；磨砂 160 ms 线性', '只淡入，不位移', 'sheet'],
  ['页头吸顶', '内容滚到页头下时，玻璃层淡入', '160 ms 线性', '直接出现', null],
  ['导航当前项', '“积釉”凹槽与短线移到新的一项', '240 ms，(.2,.7,.2,1)', '直接跳到', null],
  ['开关', '旋钮滑动，轨道转钴蓝', '200 ms', '直接切换', null],
  ['依据折叠', '高度展开，箭头翻转', '200 ms，标准曲线', '直接展开', null],
  ['遮盖', '斜纹淡入（不透明，不模糊）', '200 ms', '直接出现', null],
  ['识别进度', '当前一步的弧线转动', '1000 ms 循环', '静止，只靠文字', null],
  ['按钮按下', '缩到 0.98', '120 ms', '无', null],
]

const LEDGER_LABEL = '今日能量：早餐 412，午餐 515，加餐 158，共 1085 千卡；需要 1850 千卡'
const MODEL_TIMEOUT = new ApiError(504, 'llm_timeout', 'DeepSeek 在 30 秒内没有回应。可以重试，或到设置里换一个对话模型。')
const VISION_TIMEOUT = new ApiError(504, 'llm_timeout', '看图模型 qwen-vl-max 在 60 秒内没有回应。照片还在本页，可以直接重试。')
const STATE_CONFLICT = new ApiError(409, 'item_state_conflict', '这条医嘱已经不是生效中，请刷新后再试。')

function Swatches() {
  return (
    <section>
      <h2 className="gal-h">颜色</h2>
      <p>海军蓝一族做字，瓷白做面板，天青到冰白做背景场，钴蓝是唯一强调。三种语义色只在有结论或风险时出现，并且总配形状。</p>
      <div className="sw">
        {SWATCHES.map(([bg, name, note]) => <div key={name}><i style={{ background: bg }} /><b>{name}</b>{note}</div>)}
      </div>
    </section>
  )
}

function Type({ count }: { count: number }) {
  return (
    <section>
      <h2 className="gal-h">字体</h2>
      <p>宋体（思源宋体 700）只用于固定的页题与小节题；动态文字一律黑体。16 号以上的展示数字用 Source Serif 4，16 号以下用黑体表格数字。</p>
      <div className="ts">
        <span>44 数字</span><span className="ns" style={{ fontSize: '2.75rem', lineHeight: 1 }} data-demo="count"><CountUp value={count} /></span>
        <span>28 页题</span><Title k="records" level="display" as="h3" />
        <span>22 标题</span><Title k="resolveSheet" level="title" as="h3" />
        <span>18 小节</span><Title k="mealEval" level="h" as="h3" />
        <span>17 医嘱内容</span><span className="gal-mo-c">低盐饮食，每日钠不超过 <span className="nw">2000 毫克</span></span>
        <span>16 正文</span><span>你今天的钠已经到 1,640 毫克，离上限只剩 360 毫克。</span>
        <span>14 辅助</span><span className="t-small ink2">建议不会改变约束，只有你确认后才会解除。</span>
        <span>12 说明</span><span className="t-cap">基于最近 4 个周期，周期长度在 27 到 31 天之间。</span>
      </div>
    </section>
  )
}

function Spacing() {
  return (
    <section>
      <h2 className="gal-h">间距与圆角</h2>
      <p>间距是 4 的倍数；页边 20，面板外边 12、内边 16。圆角六级，内层圆角 = 外层圆角 − 两层之间的间距。</p>
      <div className="sp">
        {[4, 8, 12, 16, 24, 32, 48].map((n) => <div key={n}><i style={{ width: n, height: n }} />{n}</div>)}
      </div>
      <div className="radii">
        {([[6, '6 字形', '勾选框、骨架'], [10, '10 小件', '小按钮、引文'], [16, '16 控件', '按钮、输入'], [22, '22 面板', '瓷胎、开场卡'],
          [28, '28 浮层', '导航、面板'], [999, '胶囊', '开关、标签']] as const).map(([r, a, b]) => (
          <div key={r}><i style={{ borderRadius: r, width: r === 999 ? 72 : undefined }} />{a}<br />{b}</div>
        ))}
      </div>
    </section>
  )
}

function GlassSetting() {
  const [pref, setPref] = useGlassPreference()
  return (
    <RadioSegment
      label="减少透明（跟随系统 / 开 / 关）"
      value={pref}
      onChange={(v) => setPref(v as ReduceTransparencyPref)}
      options={[{ value: 'system', label: '跟随系统' }, { value: 'on', label: '开' }, { value: 'off', label: '关' }]}
    />
  )
}

export function GalleryPage() {
  const toast = useToast()
  const { setCovered } = useCover()
  const [count, setCount] = useState(1085)
  const [ledgerRun, setLedgerRun] = useState(0)
  const [switchA, setSwitchA] = useState(false)
  const [switchB, setSwitchB] = useState(true)
  const [segment, setSegment] = useState('diet')
  const [tags, setTags] = useState(['清淡'])
  const [moreTags, setMoreTags] = useState(['动物内脏', '酒精'])
  const [acked, setAcked] = useState(true)
  const [agree, setAgree] = useState(false)
  const [height, setHeight] = useState(165)
  const [weight, setWeight] = useState(56.5)
  const [healthTab, setHealthTab] = useState('medical')
  const [medicalTab, setMedicalTab] = useState('active')
  const [gender, setGender] = useState('female')
  const [username, setUsername] = useState('zhou_ning')
  const [password, setPassword] = useState('goodlife2026')
  const [baseUrl, setBaseUrl] = useState('https://dashscope.aliyuncs.com/compatible-mode/v1')
  const [health, setHealth] = useState('膝关节半月板术后（2026-08）')
  const [meal, setMeal] = useState('dinner')
  const [review, setReview] = useState<string | null>('2026-11-12')
  const [ends, setEnds] = useState<string | null>(null)
  const [sheet, setSheet] = useState<'continue' | 'confirm' | 'resolve' | 'fail' | null>(null)
  const [resolved, setResolved] = useState<string | undefined>(undefined)
  const [showDock, setShowDock] = useState(false)

  // 样张页专用：?covered=1 打开时就遮盖（与设计稿“一键遮盖”面板对照）；#编号 滚到对应区块
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('covered') === '1') setCovered(true)
    const target = window.location.hash ? document.getElementById(window.location.hash.slice(1)) : null
    target?.scrollIntoView()
  }, [setCovered])

  const closeSheet = () => {
    setSheet(null)
    setResolved(undefined)
  }
  const demo = (kind: 'count' | 'ledger' | 'sheet') => {
    if (kind === 'count') setCount((c) => (c === 1085 ? 1640 : 1085))
    if (kind === 'ledger') setLedgerRun((n) => n + 1)
    if (kind === 'sheet') setSheet('continue')
  }

  return (
    <>
      <Field />
      <main className={showDock ? 'gal with-dock' : 'gal'}>
        <PageHeader titleKey="gallery" variant="big" caption="影青 第四稿" onRefresh={() => toast.show('已刷新')} />
        <p className="gal-intro">
          全部共用组件与状态，顺序同设计稿“设计系统”一节与“状态、异常与变体”。底部是真实的浮起导航，右侧“遮盖”对整页生效。
        </p>

        <div className="gal-ds" id="ds">
          <Swatches />
          <Type count={count} />
          <Spacing />

          <section>
            <h2 className="gal-h">组件</h2>
            <p>自绘为主，行为与语义来自 react-aria-components。</p>
            <div className="comp">
              <Button variant="primary" onPress={() => toast.show('已确认入库')}>确认入库</Button>
              <Button variant="quiet" onPress={() => setSheet('continue')}>继续遵守</Button>
              <Button variant="danger" onPress={() => setSheet('resolve')}>确认解除</Button>
              <Button variant="primary" isDisabled onPress={() => {}}>确认入库</Button>
              <Button variant="text" onPress={() => {}}>去医嘱页处理</Button>
              <RefTag />
            </div>
            <div className="comp">
              <VerdictMark conclusion="suitable" />
              <VerdictMark conclusion="caution" />
              <VerdictMark conclusion="not_recommended" />
              <VerdictMark conclusion="unchecked" />
              <span className="t-small"><ConfidenceCells value={0.91} /></span>
              <span className="t-small"><ConfidenceCells value={0.72} /></span>
              <span className="t-small"><ConfidenceCells value={0.58} /></span>
            </div>
            <div className="comp">
              <Switch label="开关 关" isSelected={switchA} onChange={setSwitchA} />
              <Switch label="开关 开" isSelected={switchB} onChange={setSwitchB} />
              <RadioSegment label="分段示例" value={segment} onChange={setSegment}
                options={[{ value: 'diet', label: '饮食' }, { value: 'training', label: '训练' }]} />
              <TagField label="饮食偏好" tags={tags} onChange={setTags} />
            </div>
            <div className="gal-two">
              <div>
                <JumpCard to="/medical" label="去医嘱页处理" description="你提到医生说可以吃海鲜了。医嘱需要你本人在医嘱页处理。" />
                <Checkbox isSelected={acked} onChange={setAcked}>我知道解除后不能撤销，需要重新录入才能恢复这条约束</Checkbox>
              </div>
              <div className="gal-fieldbg">
                <SystemSlip title="医嘱提醒" lines={['按你当前生效的医嘱，以下食物不建议：麻婆豆腐。']} />
                <Surface tier="plate">
                  <EvidenceFold lines={['目标：减脂，每日能量缺口约 300 千卡', '训练：昨天有力量训练']} />
                </Surface>
              </div>
            </div>

            <h3 className="gal-sub">刻度尺（档案数据，放在敏感区里）</h3>
            <Sensitive className="plate gal-plate" style={{ paddingBottom: 10 }}>
              <Ruler label="身高" unit="厘米" value={height} onChange={setHeight} min={50} max={250} step={1} major={10} ppu={8} />
              <Ruler label="体重" unit="千克" value={weight} onChange={setWeight} min={20} max={300} step={0.5} major={5} ppu={16}
                hint="左右拖动刻度，或点数字直接输入。" />
            </Sensitive>

            <h3 className="gal-sub">按钮：全部变体与尺寸</h3>
            <div className="comp">
              <Button variant="primary" icon="camera" onPress={() => {}}>重拍</Button>
              <Button variant="quiet" icon="image" onPress={() => {}}>从相册换一张</Button>
              <Button variant="danger-outline" size="sm" onPress={() => setSheet('resolve')}>确认解除</Button>
              <Button variant="quiet" size="sm" icon="edit" onPress={() => {}}>修改</Button>
              <Button variant="primary" size="sm" onPress={() => setSheet('confirm')}>确认生效</Button>
              <Button variant="text" ink onPress={() => {}}>稍后</Button>
              <Button variant="text" icon="plus" onField onPress={() => {}}>录入医嘱</Button>
              <ButtonLink to="/medical" variant="quiet" size="sm">去医嘱页处理</ButtonLink>
              <IconButton icon="back" label="返回" back onPress={() => {}} />
              <IconButton icon="eye" label="显示密码" pressed={false} onPress={() => {}} />
              <IconButton icon="plus" label="记一次训练" onPress={() => {}} />
            </div>
            <div className="comp">
              <Button variant="primary" block onPress={() => setSheet('fail')}>确认（演示失败）</Button>
            </div>

            <h3 className="gal-sub">分段标签与文字标签</h3>
            <SegmentedTabs ariaLabel="健康" selectedKey={healthTab} onSelectionChange={setHealthTab}
              items={[{ id: 'period', label: '经期' }, { id: 'medical', label: '医嘱', badge: 2 }]} />
            <TextTabs ariaLabel="医嘱" selectedKey={medicalTab} onSelectionChange={setMedicalTab}
              items={[{ id: 'pending', label: '待核对', badge: 1 }, { id: 'active', label: '生效中 3' }, { id: 'history', label: '历史与审计' }]} />

            <h3 className="gal-sub">表单</h3>
            <Surface tier="plate" className="gal-plate" style={{ paddingBottom: 16 }}>
              <TextField label="用户名" value={username} onChange={setUsername} hint="3 到 32 位，字母、数字或下划线" autoComplete="username" />
              <PasswordField label="密码" value={password} onChange={setPassword} hint="至少 8 位" autoComplete="current-password" />
              <TextField label="服务地址" value={baseUrl} onChange={setBaseUrl} type="url" inputMode="url"
                error="请核对服务地址（例如是否少了或多了 /v1），也请确认模型编号正确。" />
              <RadioSegment label="性别" value={gender} onChange={setGender}
                options={[{ value: 'female', label: '女' }, { value: 'male', label: '男' }, { value: 'other', label: '其他' }]} />
              <SelectField label="餐次" value={meal} onChange={setMeal}
                options={[{ value: 'breakfast', label: '早餐' }, { value: 'lunch', label: '午餐' }, { value: 'dinner', label: '晚餐' }, { value: 'snack', label: '加餐' }]} />
              <DateField label="复查日期" value={review} onChange={setReview} min="2026-10-13" placeholder="不再设" />
              <DateField label="预计结束" value={ends} onChange={setEnds} placeholder="不设（长期）" />
              <TagField label="忌口" tags={moreTags} onChange={setMoreTags} />
              <TextField label="健康状况" value={health} onChange={setHealth} multiline rows={2} maxLength={500}
                hint="只用于生成建议。医生的要求请到医嘱页录入，才会按约束执行。" />
              <Checkbox isSelected={agree} onChange={setAgree}>我已阅读并理解以上内容</Checkbox>
            </Surface>

            <h3 className="gal-sub">能量账本与周期刻度</h3>
            <Surface tier="plate" className="gal-plate gal-ledger">
              <div className="gal-ledger-figs">
                <div className="gal-ledger-big"><span className="ns"><CountUp value={1085} /></span><span>/ <span className="ns">1,850</span> 千卡</span></div>
                <div className="gal-ledger-rem">还可摄入<span className="ns"><CountUp value={765} /></span></div>
              </div>
              <LedgerTicks key={ledgerRun} label={LEDGER_LABEL} need={1850}
                segments={[{ kcal: 412, tone: 1 }, { kcal: 515, tone: 2 }, { kcal: 158, tone: 3 }]} />
            </Surface>
            <Surface tier="plate" className="gal-plate" style={{ paddingTop: 6 }}>
              <CycleTicks length={29} periodDays={5} predicted={[28, 32]} today={14}
                label="周期刻度：共约 29 天，第 1 到 5 天为经期，今天第 14 天，下次预计在第 28 到 32 天之间开始" />
            </Surface>

            <h3 className="gal-sub">进度与等待</h3>
            <Surface tier="plate" className="gal-plate">
              <ol className="gal-list" aria-live="polite">
                <li><StatusMark state="ok" /><span>上传完成<small>压缩后 <span className="n">1.2</span> MB</small></span></li>
                <li><StatusMark state="running" /><span>正在认菜和份量<small>看图模型 qwen-vl-max，通常需要 5 到 15 秒</small></span></li>
                <li><StatusMark state="todo" /><span className="mute">按营养库计算热量与营养</span></li>
              </ol>
            </Surface>
            <Surface tier="plate" className="gal-plate" style={{ paddingTop: 12 }}>
              <ol className="flow">
                <li className="fs"><StatusMark state="ok" index={1} /><div><div className="fs-t">填写地址与密钥<small>已保存</small></div></div></li>
                <li className="fs"><StatusMark state="running" index={2} /><div><div className="fs-t">获取模型</div></div></li>
                <li className="fs"><StatusMark state="current" index={3} /><div><div className="fs-t">测试连通</div></div></li>
                <li className="fs off"><StatusMark state="todo" index={4} /><div><div className="fs-t">选择用途模型</div></div></li>
              </ol>
            </Surface>
            <ThoughtLine text="正在认菜和份量" />
            <WillList items={[
              { text: '这条医嘱从“生效中”变为“已解除”。' },
              { text: '记一条审计：时间、由你本人确认、依据是 10月10日 对话中的解除建议。' },
              { text: '解除不能撤销。以后需要时，请重新录入。', irreversible: true },
            ]} />

            <h3 className="gal-sub">轻提示与操作坞</h3>
            <div className="comp">
              <Button variant="quiet" onPress={() => toast.show('已清除大致区域')}>显示轻提示</Button>
              <Switch label="显示底部操作坞" isSelected={showDock} onChange={setShowDock} />
            </div>
          </section>

          <section>
            <h2 className="gal-h">材质</h2>
            <p>四种面：瓷胎（不透明，承载数据）、静玻璃（半透明不模糊，用在滚动列表里）、活玻璃（真模糊，只给固定外壳）、厚玻璃（底部面板）。降级后一律是实色。</p>
            <div className="mats">
              <div className="mat"><div className="under">背景场与内容<i /><i /></div><Surface tier="plate" className="face"><b>瓷胎 plate</b><span>不透明，#FFFFFF 到 #FBFCFE</span></Surface></div>
              <div className="mat"><div className="under">背景场与内容<i /><i /></div><Surface tier="still" className="face"><b>静玻璃 still</b><span>白 80% 到 66%，不模糊</span></Surface></div>
              <div className="mat"><div className="under">背景场与内容<i /><i /></div><Surface tier="chrome" className="face"><b>活玻璃 chrome</b><span>白 70%，模糊 16，饱和 1.4</span></Surface></div>
              <div className="mat"><div className="under">背景场与内容<i /><i /></div><Surface tier="sheet" className="face"><b>厚玻璃 sheet</b><span>白 88%，模糊 24，饱和 1.2</span></Surface></div>
              <div className="mat"><div className="under">背景场与内容<i /><i /></div><div className="face chrome gl-solid"><b>降级 solid</b><span>实色 #EAF1FA，无模糊、无颗粒</span></div></div>
            </div>
            <GlassSetting />
          </section>

          <section>
            <h2 className="gal-h">玻璃上的文字：最坏背景实测</h2>
            <p>每块都把玻璃压在它可能遇到的最亮与最暗的背景上；右下角是两行文字各自的实测值（第一行 / 第二行），完整表格见 DESIGN.md 第二节。活玻璃上最浅只用蓝灰 #33435E。</p>
            <div className="proof">
              {PROOF.map((p) => (
                <div className="pf" key={p.title}>
                  <div className="pf-bd" style={{ background: p.bg }} />
                  <Surface tier={p.tier} className="pf-g">
                    <b>{p.title}</b>
                    <span className={p.lines[0]} style={LINE_COLOR[p.lines[0]]}>{p.lines[1]}</span><br />
                    <span className={p.lines[2]} style={LINE_COLOR[p.lines[2]]}>{p.lines[3]}</span>
                    <span className="r">{p.r}</span>
                  </Surface>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="gal-h">玻璃预算</h2>
            <p>为中端安卓机定的硬上限，设计稿每一屏都守着它。</p>
            <div className="budget">
              <div><b>同屏最多 2 层模糊，硬上限 3</b>页头（吸顶后）+ 底部导航或底座；打开面板时，遮罩下的外壳停止模糊，只剩面板 1 层。</div>
              <div><b>模糊半径 16 到 24</b>外壳 16，面板 24，饱和度不超过 1.4；不叠加多层模糊。</div>
              <div><b>模糊总面积不超过视口 40%</b>对话页最大：吸顶页头约 156 像素 + 底座约 158 像素，共约 37%。</div>
              <div><b>滚动内容里不用模糊</b>列表、气泡、开场卡、附注、账目行都不用 backdrop-filter；需要“玻璃感”时用静玻璃。</div>
              <div><b>模糊半径从不做动画</b>面板滑入时是实色，停稳后磨砂用 160 ms 透明度淡入；页头吸顶同理。</div>
              <div><b>低端机整套降级</b>加载完成并空闲 1.5 秒后，在用户第一次真实滚动时量帧时间，中位数达到 24 ms 即切到实色材质；结论带版本号；“隐私与数据”里可手动改。</div>
            </div>
          </section>

          <section>
            <h2 className="gal-h">图标</h2>
            <p>一套线性图标，24 格，1.5 线宽；放在玻璃上时加粗到 1.7，抵消背后模糊带来的发虚。圆头圆角，内联 SVG。</p>
            <div className="icons">
              {ICONS.map(([name, text]) => <div key={name}><Icon name={name} />{text}</div>)}
            </div>
          </section>

          <section>
            <h2 className="gal-h">动效</h2>
            <p>只给用户动作和数字变化做动效。系统开启“减弱动态效果”时全部变成直接显示。只动 transform 与 opacity；模糊半径永远不动。</p>
            <table className="mot">
              <thead><tr><th>对象</th><th>做什么</th><th>时长与曲线</th><th>减弱动效时</th><th /></tr></thead>
              <tbody>
                {MOTION.map(([what, how, time, reduced, kind]) => (
                  <tr key={what}>
                    <td>{what}</td><td>{how}</td><td>{time}</td><td>{reduced}</td>
                    <td>{kind && <button type="button" data-demo-button={kind} onClick={() => demo(kind)}>演示</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>

        <div className="gal-states">
          <div className="gal-panel" id="st1">
            <span className="gal-cap">加载中：饮食记录</span>
            <LoadingState variant="diary" text="正在读取今天的记录" />
          </div>

          <div className="gal-panel" id="st2">
            <span className="gal-cap">失败，可重试</span>
            <ErrorState titleKey="modelFailed" error={MODEL_TIMEOUT} onRetry={() => toast.show('正在重试')}
              actions={<Button variant="quiet" onPress={() => {}}>去设置</Button>} note="你刚才发的话已保留，重试不用重新输入。" />
          </div>

          <div className="gal-panel" id="st3">
            <span className="gal-cap">无数据</span>
            <EmptyState titleKey="emptyDiary" body="拍一张饭菜，或者手动记一餐。补记的记录会算进那一天。"
              actions={<>
                <Button variant="primary" icon="camera" onPress={() => {}}>拍照记录</Button>
                <Button variant="quiet" onPress={() => {}}>手动记一餐</Button>
              </>} />
          </div>

          <div className="gal-panel" id="st4">
            <span className="gal-cap">数据不足</span>
            <InsufficientState titleKey="cycleInsufficient"
              notes={['预测至少需要 2 个完整周期，目前记录了 1 个。下次经期开始时记一笔即可。']}
              progressText="1 / 2 个周期" actions={<Button variant="quiet" onPress={() => {}}>记录经期开始</Button>} />
          </div>

          <div className="gal-panel" id="st5">
            <span className="gal-cap">需要授权：第一次查附近餐厅（只问这一次）</span>
            <AuthNeededState titleKey="locationAsk"
              body="只用来查找附近的餐厅，精确位置不会保存。不允许也没关系，可以输入地名或地标，以后不再询问。"
              actions={<div style={{ display: 'grid', gap: 10, width: '100%' }}>
                <Button variant="primary" block icon="pin" onPress={() => {}}>允许定位</Button>
                <Button variant="quiet" block onPress={() => {}}>输入地点</Button>
              </div>} />
          </div>

          <div className="gal-panel" id="st6">
            <span className="gal-cap">需要授权：未配置模型、登录过期</span>
            <AuthNeededState titleKey="noModel" body="对话和拍照识别都需要先添加一个模型服务，填地址与密钥，大约两分钟。"
              actions={<Button variant="primary" onPress={() => {}}>去添加模型服务</Button>} />
            <hr className="hr" />
            <AuthNeededState titleKey="sessionExpired" body="请重新登录，记录不会丢失。"
              actions={<Button variant="quiet" size="sm" onPress={() => {}}>重新登录</Button>} />
          </div>

          <div className="gal-panel" id="st7">
            <span className="gal-cap">拍照识别失败：看图模型超时</span>
            <ErrorState titleKey="photoFailed" error={VISION_TIMEOUT}
              actions={<>
                <Button variant="primary" icon="refresh" onPress={() => {}}>重试识别</Button>
                <Button variant="quiet" onPress={() => {}}>换一个看图模型</Button>
              </>} />
          </div>

          <div className="gal-panel" id="st8">
            <span className="gal-cap">模型服务：步骤里的另外两种失败</span>
            <div className="gal-panel-in">
              <Surface tier="plate" style={{ paddingTop: 14 }}>
                <ol className="flow" style={{ marginTop: 0 }}>
                  <li className="fs bad">
                    <StatusMark state="bad" index={2} />
                    <div>
                      <div className="fs-t">获取模型<small>地址有误</small></div>
                      <div className="err" style={{ marginTop: 2 }}><Icon name="alert" size={18} /><span>请核对服务地址（例如是否少了或多了 /v1），也请确认模型编号正确。<small>错误码 llm_bad_url</small></span></div>
                      <div style={{ marginTop: 8 }}><Button variant="quiet" size="sm" onPress={() => {}}>修改地址</Button></div>
                    </div>
                  </li>
                  <li className="fs bad">
                    <StatusMark state="bad" index={3} />
                    <div>
                      <div className="fs-t">测试连通<small>超时</small></div>
                      <div className="err" style={{ marginTop: 2 }}><Icon name="alert" size={18} /><span>qwen-plus 在 30 秒内没有回应。服务可能繁忙，稍后再试。<small>错误码 llm_timeout</small></span></div>
                      <div style={{ marginTop: 8 }}><Button variant="quiet" size="sm" icon="refresh" onPress={() => {}}>重新测试</Button></div>
                    </div>
                  </li>
                </ol>
              </Surface>
            </div>
          </div>

          <div className="gal-panel" id="st9">
            <CareBlock titleKey="careSevere" phones={['120']}
              text="你提到胸口持续发紧，伴随出汗和呼吸困难。这可能需要紧急处理。请立即拨打 120，或请身边的人陪你去最近的医院急诊。" />
            <p className="gal-note pad" style={{ margin: '16px 0 20px' }}>就医提示总在回答最上方，整块朱色，不圆角、不透明、不折叠、不可关闭；下方不再接饮食或训练建议。</p>
          </div>

          <div className="gal-panel" id="st10">
            <div className="gal-cover-top pad" style={{ paddingTop: 8 }}>
              <span className="t-cap">一键遮盖：医嘱页</span>
              <CoverButton />
            </div>
            <div className="gal-panel-in" style={{ paddingTop: 0 }}>
              <Sensitive className="plate">
                <div className="gmo"><div className="gmo-h"><span className="gmo-cat">饮食禁忌</span><span className="gmo-st">生效中</span></div><div className="gal-mo-c">避免动物内脏与浓肉汤（高嘌呤）</div></div>
                <div className="gmo"><div className="gmo-h"><span className="gmo-cat">运动限制</span><span className="gmo-st">生效中</span></div><div className="gal-mo-c">膝关节术后六周内避免跑跳</div>
                  <div className="acts"><Button variant="quiet" size="sm" onPress={() => {}}>继续遵守</Button></div></div>
              </Sensitive>
              <p className="gal-note">遮盖是不透明的斜纹，跟随面板圆角，盖住内容但保留版面；绝不用模糊遮盖。遮盖时敏感区同时对读屏隐藏并设 inert。应用切到后台再回来时默认遮盖。</p>
            </div>
          </div>

          <div className="gal-panel" id="st11">
            <span className="gal-cap">导航变体</span>
            <div className="gal-panel-in">
              <p className="gal-st-p" style={{ marginTop: 0 }}>四项加遮盖（默认），浮在内容上方：</p>
              <div className="navdemo" style={{ marginTop: 6 }}>
                <div className="under">早餐 412 千卡，燕麦牛奶粥一碗……<br /><b>确认入库</b></div>
                <BottomNav items={SHELL_NAV} />
              </div>
              <p className="gal-st-p" style={{ marginTop: 16 }}>没有经期也没有医嘱模块时，“健康”整项隐藏，变成三项；当前项的“积釉”凹槽仍在当前项正中：</p>
              <div className="navdemo" style={{ marginTop: 6 }}>
                <div className="under">午餐 515 千卡，米饭一碗……<br /><b>记录今天</b></div>
                <BottomNav items={NAV_THREE} />
              </div>
              <p className="gal-st-p" style={{ marginTop: 16 }}>只有医嘱、没有经期时，“健康”页不显示经期与医嘱的分段控件，标题仍是“健康”，直接列出医嘱的三个子标签。</p>
            </div>
          </div>

          <div className="gal-panel" id="st12">
            <span className="gal-cap">玻璃降级：同一条导航的两种材质</span>
            <div className="gal-panel-in">
              <div className="gl-pair">
                <div><div className="under">今天已摄入钠 1,640 毫克<i /></div><span className="glc">磨砂</span>
                  <Surface tier="chrome" className="face"><b>记录</b><span>健康</span><span>我的</span></Surface></div>
                <div><div className="under">今天已摄入钠 1,640 毫克<i /></div><span className="glc">实色降级</span>
                  <div className="face chrome gl-solid"><b>记录</b><span>健康</span><span>我的</span></div></div>
              </div>
              <p className="gal-st-p">活玻璃是 70% 白、模糊 16：左边能看到下面那条钴蓝被柔化成一片青光，右边是实色。降级时玻璃换成实色的浅青瓷面（#EAF1FA），保留高光边、细线与投影。触发条件：浏览器不支持 backdrop-filter；系统开启“减少透明度”；“减少透明”设置打开；判定为低端机；强制颜色模式下退成系统色。</p>
            </div>
          </div>
        </div>
      </main>

      <Sheet isOpen={sheet === 'continue'} onClose={closeSheet} titleKey="continueSheet"
        footer={<>
          <Button variant="primary" block onPress={closeSheet}>继续遵守</Button>
          <Button variant="quiet" block onPress={closeSheet}>取消</Button>
        </>}>
        <div className="quote"><span className="t-cap">饮食要求</span><div className="gal-mo-c" style={{ margin: '4px 0 2px' }}>低盐饮食，每日钠不超过 <span className="nw">2000 毫克</span></div><span className="t-cap">生效 2026-07-12</span></div>
        <p className="t-small" style={{ margin: '12px 0 0' }}>两个日期一起提交，留空的一项会被清除。</p>
        <DateField label="复查日期" value={review} onChange={setReview} min="2026-10-13" placeholder="不再设" />
        <DateField label="预计结束" value={ends} onChange={setEnds} placeholder="不设（长期）" />
        <WillList items={[
          { text: '状态从“待复核”回到“生效中”，饮食建议继续按它约束。' },
          { text: `复查日期改为 ${review ?? '不再设'}，那天打开应用时会再次提醒复核。` },
          { text: '预计结束保持不设，继续长期有效。如果填了日期，到期前一天进入待复核。' },
          { text: '记一条审计：时间、由你本人确认、两个新日期。' },
        ]} />
      </Sheet>
      <ConfirmSheet isOpen={sheet === 'confirm'} onClose={closeSheet} titleKey="confirmSheet"
        quote={<><span className="t-cap">用药相关饮食注意</span><div className="gal-mo-c" style={{ margin: '4px 0' }}>服药期间及停药后 7 天内禁止饮酒</div><span className="t-cap">来源：出院小结（图片），提取把握 中</span></>}
        will={[
          { text: '状态从“待核对”变为“生效中”。' },
          { text: '之后的对话、拍照评价和附近餐厅推荐都按它约束，酒类和含酒精的菜会标为不建议。' },
          { text: '预计结束 2026-10-25。结束前一天（10月24日）起进入待复核，那天打开应用时会提醒你。' },
          { text: '记一条审计：时间、由你本人确认、来源与修改过的字段。' },
        ]}
        confirmLabel="确认生效" secondary={{ label: '返回修改', onPress: closeSheet }}
        note="医嘱只能在这里确认或解除，对话里无法完成。"
        onConfirm={async () => {
          await new Promise((resolve) => setTimeout(resolve, 600))
          closeSheet()
          toast.show('已确认生效')
        }} />
      <ConfirmSheet isOpen={sheet === 'resolve'} onClose={closeSheet} titleKey="resolveSheet"
        quote={<><span className="t-cap">运动限制</span><div className="gal-mo-c" style={{ margin: '4px 0' }}>膝关节术后六周内避免跑跳</div><span className="t-cap">来源：2026-09-05 出院小结（图片）</span></>}
        will={[
          { text: '这条医嘱从“生效中”变为“已解除”。' },
          { text: '之后的训练与饮食建议不再按它约束，开合跳、慢跑等不再提示冲突。' },
          { text: '记一条审计：时间、由你本人确认、依据是 10月10日 对话中的解除建议。' },
          { text: '解除不能撤销。以后需要时，请重新录入。', irreversible: true },
        ]}
        ack="我知道解除后不能撤销，需要重新录入才能恢复这条约束"
        confirmLabel="确认解除" confirmVariant="danger"
        secondary={{ label: '不解除，撤销这条建议', onPress: closeSheet }}
        note="医嘱只能在这里确认或解除，对话里无法完成。" resultText={resolved}
        onConfirm={async () => {
          await new Promise((resolve) => setTimeout(resolve, 600))
          setResolved('已解除：膝关节术后六周内避免跑跳。审计已记录。')
        }} />
      <ConfirmSheet isOpen={sheet === 'fail'} onClose={closeSheet} titleKey="resolveSheet"
        quote={<div className="gal-mo-c">膝关节术后六周内避免跑跳</div>}
        confirmLabel="确认解除" confirmVariant="danger" error={STATE_CONFLICT}
        note="医嘱只能在这里确认或解除，对话里无法完成。" onConfirm={() => Promise.resolve()} />

      {showDock ? (
        <Dock tall>
          <Checkbox isSelected={agree} onChange={setAgree}>我已阅读并理解以上内容</Checkbox>
          <Button variant="primary" block isDisabled={!agree} onPress={() => toast.show('已确认')}>确认并继续</Button>
        </Dock>
      ) : (
        <ShellPortal><BottomNav items={SHELL_NAV} /></ShellPortal>
      )}
    </>
  )
}
