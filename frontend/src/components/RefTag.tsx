import { REFERENCE_LABEL } from '../lib/contract'
import '../styles/components/ref.css'

/** “仅供参考”：全站同一个样子。 */
export function RefTag() {
  return <span className="ref">{REFERENCE_LABEL}</span>
}
