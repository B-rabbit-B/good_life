import { useId } from 'react'
import type { PhotoEvaluationOut } from '../../api/types'
import { RefTag } from '../../components/RefTag'
import { Sensitive } from '../../components/Sensitive'
import { Title } from '../../components/Title'
import { VerdictMark } from '../../components/VerdictMark'
import { SOURCE_NAMES } from '../../lib/contract'
import { CONCLUSION_LABELS } from '../../lib/labels'

/**
 * 整餐评价（只给草稿，后端确认后不再评价）：结论大字；每项菜的每条依据一行（这道菜的结论形状加菜名、来源、原文）；
 * 有取舍说明时写在那道菜下面；没核对的菜品提示放在虚线框里；最后是引擎的免责句。全部原样来自后端。
 */
export function MealEvaluation({ evaluation }: { evaluation: PhotoEvaluationOut }) {
  const id = useId()
  return (
    <Sensitive as="section" area="evaluation" className="plate" aria-labelledby={id}>
      <div className="eval-h">
        <Title k="mealEval" level="h" id={id} />
        <RefTag />
      </div>
      <div className={`verdict ${evaluation.conclusion}`}>
        <b>{CONCLUSION_LABELS[evaluation.conclusion]}</b>
      </div>
      {evaluation.items.map((item) => (
        <div key={item.item_id}>
          {item.reasons.map((reason) => (
            <div key={`${reason.source}-${reason.code}-${reason.ref}-${reason.message}`} className="reason">
              <VerdictMark conclusion={item.conclusion} label={item.food_name} />
              <p><span className="src">{SOURCE_NAMES[reason.source] ?? reason.source}</span>{reason.message}</p>
            </div>
          ))}
          {item.tradeoff && <p className="tradeoff">{item.tradeoff}</p>}
        </div>
      ))}
      {evaluation.unchecked_notice && <p className="unchecked">{evaluation.unchecked_notice}</p>}
      <p className="t-cap eval-disc">{evaluation.disclaimer}</p>
    </Sensitive>
  )
}
