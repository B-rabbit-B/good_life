// 附近餐厅的测试数据：需求词表与说明照抄后端（app/restaurants/data/needs.json、service.NOTICE、引擎的 DISCLAIMER），
// 检索结果仿照设计稿 09：四家店（适合、注意两家、未核对一家）与两个已避开的类型。
import type { NeedOut, RestaurantSearchOut, RestaurantSettingsOut } from '../../api/types'

export const NOTICE = '到店可点与应避开是基于餐厅类别的一般性建议，不代表该店真实菜单，也不保证该店有这些菜。'
export const ENGINE_DISCLAIMER = '以上判断基于规则与营养数据，仅供参考，不构成医疗建议；有医嘱时以医嘱为准。'
export const UNCHECKED_TIP = '无法判断这家店的类别，请到店自行留意。'
export const NOT_GRANTED_MESSAGE = '没有定位授权，可以直接输入地点（地名或地标，可加上城市）来查找附近餐厅。'
export const PLACE_NOT_FOUND_MESSAGE = '没有找到这个地点，请换个说法（例如附近的地标或街道），或加上所在城市再试。'

export const NEEDS: NeedOut[] = [
  ['light', '清淡', '口味清淡、好消化，适合胃不舒服或没胃口的时候'],
  ['porridge', '粥', '粥铺、砂锅粥一类，暖胃好消化'],
  ['soup', '汤', '想喝口热汤'],
  ['light_meal', '轻食', '沙拉、轻食一类，热量较低'],
  ['high_protein', '高蛋白', '多一些肉蛋鱼虾，适合健身、增肌之后'],
  ['vegetarian', '素食', '不吃肉，素菜为主'],
  ['noodles', '面食', '面条、米线、米粉一类'],
  ['not_spicy', '不辣', '不吃辣或不能吃辣'],
  ['less_oil', '少油', '少油不油腻'],
  ['dumpling', '饺子包子', '饺子、馄饨、包子一类'],
  ['halal', '清真', '清真餐厅'],
  ['dessert', '甜品', '甜品、蛋糕、奶茶等饮品'],
].map(([key, name, description]) => ({ key: key ?? '', name: name ?? '', description: description ?? '' }))

export function restaurantSettings(over: Partial<RestaurantSettingsOut> = {}): RestaurantSettingsOut {
  const consent = over.location_consent ?? 'not_asked'
  return { location_consent: consent, should_ask_location: consent === 'not_asked', area: null, ...over }
}

export const SAVED_AREA = { name: '朝阳区', saved_at: '2026-10-10T08:00:00Z' }

const nav = (id: string) => `https://uri.amap.com/marker?position=116.46,39.91&name=${id}&src=goodlife`

export function searchResult(over: Partial<RestaurantSearchOut> = {}): RestaurantSearchOut {
  return {
    center: { name: '国贸', source: 'place' },
    needs: { keys: [], names: [], source: 'none' },
    restaurants: [
      {
        id: 'D003', name: '张记粥铺', type_key: 'porridge', type_name: '粥铺', distance_m: 320, rating: 4.2,
        address: '建国门外大街 1 号', conclusion: 'suitable', nav_url: nav('D003'), tip: null,
      },
      {
        id: 'D101', name: '岭南小馆', type_key: 'cantonese', type_name: '粤菜', distance_m: 650, rating: null,
        address: '建国门外大街 2 号', conclusion: 'caution', nav_url: nav('D101'), tip: null,
      },
      {
        id: 'D006', name: '张姐面馆', type_key: 'noodles', type_name: '面馆', distance_m: 1480, rating: null,
        address: '建国门外大街 3 号', conclusion: 'caution', nav_url: nav('D006'), tip: null,
      },
      {
        id: 'D007', name: '某某餐厅', type_key: null, type_name: null, distance_m: 900, rating: null,
        address: '建国门外大街 4 号', conclusion: 'unchecked', nav_url: nav('D007'), tip: UNCHECKED_TIP,
      },
    ],
    type_advice: [
      { type_key: 'porridge', type_name: '粥铺', conclusion: 'suitable', order: ['小米南瓜粥', '白灼菜心', '蒸蛋羹'], moderate: [], avoid: [], reasons: [] },
      { type_key: 'cantonese', type_name: '粤菜', conclusion: 'caution', order: ['清蒸鱼', '白灼时蔬'], moderate: ['烧味', '煲仔饭'], avoid: [], reasons: [] },
      { type_key: 'noodles', type_name: '面馆', conclusion: 'caution', order: ['清汤面'], moderate: [], avoid: ['浓汤底拉面'], reasons: [] },
      {
        type_key: 'hotpot', type_name: '火锅', conclusion: 'not_recommended', order: [], moderate: [], avoid: ['火锅（浓汤底）'],
        reasons: [{
          food_name: '火锅（浓汤底）', code: 'medical_avoid', effect: 'block', message: '避免动物内脏与浓肉汤（高嘌呤）',
          ref: 'medical:1', source: 'medical',
        }],
      },
    ],
    avoided_types: [
      {
        type_key: 'hotpot', type_name: '火锅', restaurants: ['老码头火锅'],
        reasons: [{
          food_name: '火锅（浓汤底）', code: 'medical_avoid', effect: 'block', message: '避免动物内脏与浓肉汤（高嘌呤）',
          ref: 'medical:1', source: 'medical',
        }],
      },
      {
        type_key: 'malatang', type_name: '麻辣烫与串串', restaurants: ['杨记麻辣烫', '串串香'],
        reasons: [{
          food_name: '麻辣烫', code: 'intake_sodium', effect: 'caution', message: '今天的钠已到 1,640 毫克，再吃一份预计超过上限',
          ref: 'intake:sodium', source: 'intake',
        }],
      },
    ],
    notice: NOTICE,
    disclaimer: ENGINE_DISCLAIMER,
    ...over,
  }
}
