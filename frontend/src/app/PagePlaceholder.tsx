import { PageHeader } from '../components/PageHeader'
import type { TitleKey } from '../lib/titles'
import '../styles/components/app-shell.css'

/** 页面占位：页头加一行说明；各页面任务把它换成真正的页面。 */
export function PagePlaceholder({ titleKey, variant = 'big', back }: {
  titleKey: TitleKey
  variant?: 'big' | 'sub' | 'chat'
  back?: true | string
}) {
  return (
    <>
      <PageHeader titleKey={titleKey} variant={variant} back={back} />
      <p className="ph-note">这一页还在制作中。</p>
    </>
  )
}
