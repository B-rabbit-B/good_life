// 我的（设计稿 13a）：用户名与注册日期；档案摘要（三列事实格、忌口与健康状况）；修改档案；两个开关（主动提问、经期记录）；
// 设置链接（模型服务、隐私与数据、免责声明）；退出登录。档案摘要与两个开关在敏感区里。
// 经期记录开关只给女性用户；切换后由后端的能力清单决定导航（useUpdateProfile 等能力清单刷新完才算完成）。
import { Link } from 'react-router'
import { useAgentSettings, useUpdateAgentSettings } from '../../api/hooks/agent'
import { useMe } from '../../api/hooks/auth'
import { useLogout } from '../../app/useLogout'
import { useDisclaimerStatus } from '../../api/hooks/disclaimer'
import { useAssignments, useProviders } from '../../api/hooks/llm'
import { useProfile, useUpdateProfile } from '../../api/hooks/profile'
import type { AssignmentOut, ProfileOut, ProviderOut } from '../../api/types'
import { useSensitivePage } from '../../app/AppShell'
import { PATHS } from '../../app/paths'
import { Button } from '../../components/Button'
import { ButtonLink } from '../../components/ButtonLink'
import { Icon } from '../../components/Icon'
import { PageHeader } from '../../components/PageHeader'
import { Sensitive } from '../../components/Sensitive'
import { LoadingState } from '../../components/states/LoadingState'
import { Switch } from '../../components/Switch'
import { useToast } from '../../components/Toast'
import { todayISO } from '../../lib/dates'
import { fmtNum } from '../../lib/format'
import { ACTIVITY_LABELS, GENDER_LABELS, GOAL_LABELS } from '../../lib/labels'
import '../../styles/components/me.css'

const MISSING = '未填'

function Facts({ profile: p }: { profile: ProfileOut }) {
  const unit = (value: number | null, suffix: string) =>
    value === null ? MISSING : <><span className="ns">{fmtNum(value, 1)}</span> {suffix}</>
  return (
    <div className="facts">
      <div>出生年份{p.birth_year === null ? <b>{MISSING}</b> : <b className="ns">{p.birth_year}</b>}</div>
      <div>性别<b>{p.gender ? GENDER_LABELS[p.gender] : MISSING}</b></div>
      <div>活动水平<b>{p.activity_level ? ACTIVITY_LABELS[p.activity_level] : MISSING}</b></div>
      <div>身高<b>{unit(p.height_cm, '厘米')}</b></div>
      <div>体重<b>{unit(p.weight_kg, '千克')}</b></div>
      <div>目标<b>{p.goal ? GOAL_LABELS[p.goal] : MISSING}</b></div>
    </div>
  )
}

function OpeningsSwitch() {
  const settings = useAgentSettings()
  const update = useUpdateAgentSettings()
  const toast = useToast()
  if (!settings.data) {
    if (!settings.isError) return null
    return (
      <div className="tg-row">
        <span>打开应用时主动提问<small>{settings.error.message}</small></span>
        <Button variant="text" onPress={() => void settings.refetch()}>重试</Button>
      </div>
    )
  }
  const selected = update.isPending && update.variables ? update.variables.openings_enabled : settings.data.openings_enabled
  return (
    <Switch
      label="打开应用时主动提问" description="每天最多问一个问题" isSelected={selected}
      onChange={(openings_enabled) => update.mutate({ openings_enabled }, { onError: (error) => toast.show(error.message) })}
    />
  )
}

function CycleSwitch({ profile }: { profile: ProfileOut }) {
  const update = useUpdateProfile()
  const toast = useToast()
  const optOut = update.isPending && update.variables?.cycle_tracking_opt_out != null
    ? update.variables.cycle_tracking_opt_out
    : profile.cycle_tracking_opt_out
  return (
    <Switch
      label="经期记录" description="关闭后隐藏经期入口，已有记录保留" isSelected={!optOut}
      onChange={(on) => update.mutate({ cycle_tracking_opt_out: !on }, { onError: (error) => toast.show(error.message) })}
    />
  )
}

/** 模型服务一行右侧的摘要：“N 个，对话已设置”，没有服务时“未设置” */
function modelSummary(providers: ProviderOut[], assignments: AssignmentOut[]): string {
  if (providers.length === 0) return '未设置'
  return `${providers.length} 个，对话${assignments.some((a) => a.purpose === 'chat') ? '已' : '未'}设置`
}

function SettingLinks() {
  const providers = useProviders()
  const assignments = useAssignments()
  const status = useDisclaimerStatus()
  const models = providers.data && assignments.data
    ? modelSummary(providers.data, assignments.data)
    : providers.isError || assignments.isError ? '没能读取' : ''
  const disclaimer = status.data?.accepted ? `已确认 ${status.data.current_version} 版` : ''
  const row = (to: string, label: string, value: string) => (
    <Link className="lnk" to={to}>
      {label}
      <span className="v">{value}</span>
      <Icon name="right" />
    </Link>
  )
  return (
    <div className="plate me-links">
      {row(PATHS.models, '模型服务', models)}
      {row(PATHS.privacy, '隐私与数据', '含“减少透明”')}
      {row(PATHS.disclaimerView, '免责声明', disclaimer)}
    </div>
  )
}

export default function MePage() {
  useSensitivePage('me')
  const me = useMe()
  const profile = useProfile()
  const logout = useLogout()
  const p = profile.data

  return (
    <>
      <PageHeader titleKey="me" variant="big" />
      {!p ? <LoadingState variant="list" text="正在读取档案" /> : (
        <>
          <div className="me-id">
            {me.data && (
              <>
                <b>{me.data.username}</b>
                <span className="t-cap">注册于 {todayISO(new Date(me.data.created_at))}</span>
              </>
            )}
          </div>
          <Sensitive area="profile" className="plate me-profile">
            <Facts profile={p} />
            <div className="me-more">
              <p className="t-small"><span className="mute">{'忌口　'}</span>{p.food_avoidances.join('、') || MISSING}</p>
              <p className="t-small"><span className="mute">{'健康状况　'}</span>{p.health_conditions || MISSING}</p>
            </div>
          </Sensitive>
          <div className="pad me-edit">
            <ButtonLink to={PATHS.profileEdit} variant="quiet" block>
              <Icon name="edit" size={18} />
              修改档案
            </ButtonLink>
          </div>
          <Sensitive area="switches" className="plate me-switches">
            <OpeningsSwitch />
            {p.gender === 'female' && <CycleSwitch profile={p} />}
          </Sensitive>
          <SettingLinks />
          <div className="me-out">
            <Button variant="text" ink isPending={logout.isPending} onPress={() => logout.mutate()}>退出登录</Button>
          </div>
        </>
      )}
    </>
  )
}
