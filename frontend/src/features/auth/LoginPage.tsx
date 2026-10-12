// 登录与注册（设计稿 01）：分段切换登录与注册；注册成功立即登录，然后去免责页。
// 两句提示只是界面说明，是否合格以后端为准：后端的字段说明原样写在对应字段下面，用户名或密码错误写在表单上。
import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { useLogin, useRegister } from '../../api/hooks/auth'
import type { LoginState } from '../../app/guards'
import { PATHS } from '../../app/paths'
import { Button } from '../../components/Button'
import { PasswordField } from '../../components/PasswordField'
import { SegmentedTabs } from '../../components/SegmentedTabs'
import { AuthNeededState } from '../../components/states/AuthNeededState'
import { TextField } from '../../components/TextField'
import { Title } from '../../components/Title'
import '../../styles/components/login.css'
import { errorsOf, otherErrors } from '../onboarding/fieldErrors'
import { FormError } from '../onboarding/FormError'

type Mode = 'login' | 'register'

const MODES = [{ id: 'login', label: '登录' }, { id: 'register', label: '注册' }]
const FIELDS = ['username', 'password'] as const

export default function LoginPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as LoginState | null
  const login = useLogin()
  const register = useRegister()
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [pending, setPending] = useState(false)
  const registering = mode === 'register'

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (pending) return
    setErrors({})
    setPending(true)
    const body = { username, password }
    try {
      if (registering) await register.mutateAsync(body)
      await login.mutateAsync(body)
      await navigate(registering ? PATHS.disclaimer : (state?.from ?? PATHS.root), { replace: true })
    } catch (error) {
      setErrors(errorsOf(error))
      setPending(false)
    }
  }

  const switchMode = (next: string) => {
    setMode(next === 'register' ? 'register' : 'login')
    setErrors({})
  }

  return (
    <div className="login">
      {state?.expired && (
        <div className="plate login-expired">
          <AuthNeededState titleKey="sessionExpired" body="请重新登录，记录不会丢失。" />
        </div>
      )}
      <div className="wm"><b>good-life</b><span>个人档案驱动的健康生活助手</span></div>
      <div className="login-h"><Title k={mode} level="display" as="h1" /></div>
      <p className="login-p">之后的饮食、训练与医嘱记录，都只保存在你的账号下。</p>
      <form className="plate login-plate" noValidate onSubmit={(event) => void submit(event)}>
        <SegmentedTabs items={MODES} selectedKey={mode} onSelectionChange={switchMode} ariaLabel="登录或注册" />
        {/* 按模式重新挂载：React Aria 只在挂载与出错状态变化时登记说明文字，注册模式才有的提示要随之读出 */}
        <TextField
          key={`username-${mode}`}
          label="用户名" value={username} onChange={setUsername} autoComplete="username"
          hint={registering ? '3 到 32 位，字母、数字或下划线' : undefined} error={errors.username}
        />
        <PasswordField
          key={`password-${mode}`}
          label="密码" value={password} onChange={setPassword}
          autoComplete={registering ? 'new-password' : 'current-password'}
          hint={registering ? '至少 8 位' : undefined} error={errors.password}
        />
        <FormError messages={otherErrors(errors, FIELDS)} />
        <div className="login-submit">
          <Button variant="primary" block type="submit" isPending={pending} onPress={() => undefined}>
            {registering ? '注册并继续' : '登录'}
          </Button>
        </div>
        {registering && <p className="t-cap login-next">下一步会请你阅读并确认免责声明，确认后才能开始使用。</p>}
      </form>
      <p className="foot-note">只提供生活方式建议，不做医疗诊断，不替代医生。</p>
    </div>
  )
}
