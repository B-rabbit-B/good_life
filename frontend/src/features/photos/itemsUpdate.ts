// 识别项的修正请求：后端按整组替换（PUT items），没出现的项即删除。
// 按 app/photos/service.py::_revise 的规则：只发编号与菜名的项原样保留；原来有食物编号的再带上它，
// 否则用户从候选里选的食物会被当成“按菜名重新匹配”。改动的那一项发改动的字段；
// 只改份量或克数时仍带上原来的食物编号（菜名没变，选过的食物不该丢），改了菜名就按新名字重新匹配。
// 克数可以是用户填的原文（不是有限的数字时原样发出，让后端给出说明），所以请求体是 PhotoItemPatch。
import type { PhotoItemPatch } from '../../api/hooks/photos'
import type { PhotoItemOut } from '../../api/types'

export type ItemChange =
  | { kind: 'edit'; id: string; name?: string; grams?: number | string; portion_text?: string; food_id?: string }
  | { kind: 'delete'; id: string }

const keep = (item: PhotoItemOut): PhotoItemPatch =>
  item.food_id ? { id: item.id, name: item.name, food_id: item.food_id } : { id: item.id, name: item.name }

function edited(item: PhotoItemOut, change: Extract<ItemChange, { kind: 'edit' }>): PhotoItemPatch {
  const renamed = change.name !== undefined && change.name !== item.name
  const body: PhotoItemPatch = { id: item.id, name: change.name ?? item.name }
  if (change.portion_text !== undefined) body.portion_text = change.portion_text
  if (change.grams !== undefined) body.grams = change.grams
  if (change.food_id !== undefined) body.food_id = change.food_id
  else if (!renamed && item.food_id) body.food_id = item.food_id
  return body
}

export function toItemsUpdate(items: PhotoItemOut[], change: ItemChange): PhotoItemPatch[] {
  if (change.kind === 'delete') return items.filter((item) => item.id !== change.id).map(keep)
  return items.map((item) => (item.id === change.id ? edited(item, change) : keep(item)))
}
