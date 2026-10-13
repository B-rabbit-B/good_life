import titlesJson from './titles.json'

/** 全部写死的宋体标题。宋体子集只含这些字加 SERIF_EXTRA；新增标题要在 titles.json 加键并重新运行 pnpm fonts。 */
export const TITLES = titlesJson
export type TitleKey = keyof typeof TITLES

/** 标题里可能夹带的数字与标点，也放进宋体子集。 */
export const SERIF_EXTRA = '0123456789年月日，、：；（）·—/- '
