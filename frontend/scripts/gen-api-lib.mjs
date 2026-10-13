import openapiTS, { astToString } from 'openapi-typescript'

export const GENERATED_HEADER = '// 由 pnpm api:gen 生成，不要手改\n'

/** 由 OpenAPI 文档生成 src/api/schema.d.ts 的全文（键按字母排序，结果只取决于文档本身）。 */
export async function generateSchemaSource(openapi) {
  // openapi-typescript 会改写传入的对象，先复制一份
  const nodes = await openapiTS(structuredClone(openapi), { alphabetize: true })
  return GENERATED_HEADER + astToString(nodes)
}
