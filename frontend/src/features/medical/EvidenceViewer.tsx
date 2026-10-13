import { useEffect, useRef } from 'react'
import { useEvidenceBlob } from '../../api/hooks/medicalPage'
import { useObjectUrl } from '../../api/hooks/photos'
import type { EvidenceOut, OrderOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Icon } from '../../components/Icon'
import { Sensitive } from '../../components/Sensitive'
import { Sheet } from '../../components/Sheet'
import { fmtBytes } from '../../lib/format'
import '../../styles/components/field-input.css'
import '../../styles/components/medical.css'

function EvidenceImage({ blob, alt }: { blob: Blob; alt: string }) {
  const ref = useObjectUrl(blob)
  return <img ref={ref} alt={alt} />
}

/** PDF：生成 object URL 写到链接上，在新标签页打开（不强制下载；卸载时释放） */
function EvidenceLink({ blob }: { blob: Blob }) {
  const ref = useRef<HTMLAnchorElement>(null)
  useEffect(() => {
    const link = ref.current
    if (!link || typeof URL.createObjectURL !== 'function') return undefined
    const url = URL.createObjectURL(blob)
    link.href = url
    return () => {
      link.removeAttribute('href')
      URL.revokeObjectURL(url)
    }
  }, [blob])
  return <a ref={ref} className="btn btn-qt btn-sm" data-hit44="" target="_blank" rel="noopener">打开文件</a>
}

function EvidenceFile({ file }: { file: EvidenceOut }) {
  const { blob, error } = useEvidenceBlob(file.id)
  const image = file.content_type.startsWith('image/')
  return (
    <li className="ev-file">
      <span>{file.filename}</span>
      <span className="t-cap">{fmtBytes(file.size_bytes)}，加密保存</span>
      {error && (
        <div className="err" role="alert">
          <Icon name="alert" size={18} />
          <span>{error.message}<small>错误码 {error.code}</small></span>
        </div>
      )}
      {!error && !blob && <span className="t-cap">正在读取</span>}
      {blob && (image ? <EvidenceImage blob={blob} alt={file.filename} /> : <EvidenceLink blob={blob} />)}
    </li>
  )
}

/** 原文与证据：这份医嘱的开具日期、原文（照录入时的样子）与加密保存的证据文件（图片直接显示，PDF 可打开）。 */
export function EvidenceViewer({ order, isOpen, onClose }: { order: OrderOut; isOpen: boolean; onClose: () => void }) {
  return (
    <Sheet isOpen={isOpen} onClose={onClose} title="原文与证据">
      <Sensitive area="content" className="ev-view">
        <p className="t-cap">开具日期 {order.order_date}</p>
        <div className="orig">{order.source_text}</div>
        {order.evidence.length > 0 && (
          <ul className="ev-files">{order.evidence.map((file) => <EvidenceFile key={file.id} file={file} />)}</ul>
        )}
      </Sensitive>
      <div className="sheet-foot">
        <Button variant="quiet" block onPress={onClose}>关闭</Button>
      </div>
    </Sheet>
  )
}
