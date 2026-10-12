// 建档（设计稿 02 与 DESIGN.md 第十三节的线框）：/onboarding/1 基本信息、/2 活动与目标、/3 饮食偏好与忌口（可跳过）。
// 每一步“下一步”先提交本步的字段再前进；第 3 步完成或跳过后进入对话。打开的那一步前面还有没填完的，回到第一个没填完的一步
// （“填完”的判断与守卫相同，见 app/profile.ts）。
import { Navigate, useNavigate, useParams } from 'react-router'
import type { ApiError } from '../../api/errors'
import { useProfile } from '../../api/hooks/profile'
import { onboardingPath, PATHS } from '../../app/paths'
import { firstIncompleteStep, isProfileComplete } from '../../app/profile'
import { PageHeader } from '../../components/PageHeader'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import '../../styles/components/onboarding.css'
import { StepActivity } from './StepActivity'
import { StepBasics } from './StepBasics'
import { StepDiet } from './StepDiet'

type Step = 1 | 2 | 3

const STEP_NAMES: Record<Step, string> = { 1: '基本信息', 2: '活动与目标', 3: '饮食偏好与忌口' }
const STEPS: Step[] = [1, 2, 3]

const parseStep = (value: string | undefined): Step | null =>
  value === '1' ? 1 : value === '2' ? 2 : value === '3' ? 3 : null

function Progress({ step }: { step: Step }) {
  return (
    <div className="steps" role="group" aria-label={`建档进度，第 ${step} 步，共 3 步`}>
      {STEPS.map((n) => (
        <div key={n} className={n < step ? 'step done' : 'step'} aria-current={n === step ? 'step' : undefined}>
          {`${n} ${STEP_NAMES[n]}`}
        </div>
      ))}
    </div>
  )
}

export default function OnboardingPage() {
  const params = useParams()
  const navigate = useNavigate()
  const profile = useProfile()
  const requested = parseStep(params.step)

  if (!profile.data) {
    return (
      <>
        <PageHeader variant="sub" />
        {profile.isError
          ? <ErrorState error={profile.error as ApiError} onRetry={() => void profile.refetch()} />
          : <LoadingState variant="page" text="正在读取档案" />}
      </>
    )
  }

  // 第 3 步可以跳过，所以六项都填了时三步都能打开
  const furthest: Step = isProfileComplete(profile.data) ? 3 : firstIncompleteStep(profile.data)
  if (requested === null || requested > furthest) return <Navigate to={onboardingPath(furthest)} replace />
  const step = requested

  return (
    <>
      <PageHeader variant="sub" back={step > 1 ? onboardingPath((step - 1) as 1 | 2) : undefined}>
        <Progress step={step} />
      </PageHeader>
      {step === 1 && <StepBasics profile={profile.data} onSaved={() => void navigate(onboardingPath(2))} />}
      {step === 2 && <StepActivity profile={profile.data} onSaved={() => void navigate(onboardingPath(3))} />}
      {step === 3 && <StepDiet profile={profile.data} onDone={() => void navigate(PATHS.chat, { replace: true })} />}
    </>
  )
}
