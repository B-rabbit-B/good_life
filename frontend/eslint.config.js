import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'
import tseslint from 'typescript-eslint'

const ANIMATION_LIBRARIES = ['framer-motion', 'motion', 'gsap', 'react-spring', 'animejs', 'react-bits']
const NO_ANIMATION = '不引入动画库：动效只用 CSS 与 Web Animations API'
const NO_EVENT_SOURCE = '用 src/api/sse.ts'

/** 动画库一律禁止；extraPaths 用于在某些目录再加禁止项（同一条规则的选项在后面的配置里会整体覆盖，所以一起生成）。 */
const restrictedImports = (extraPaths = []) => ['error', {
  paths: [...ANIMATION_LIBRARIES.map((name) => ({ name, message: NO_ANIMATION })), ...extraPaths],
  patterns: [{ group: ['@react-spring/*', ...ANIMATION_LIBRARIES.map((name) => `${name}/*`)], message: NO_ANIMATION }],
}]

export default tseslint.config(
  { ignores: ['dist', 'dist-e2e', 'src/api/schema.d.ts', 'playwright-report', 'test-results', 'blob-report'] },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  reactHooks.configs.flat.recommended,
  {
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      'no-restricted-globals': ['error', { name: 'EventSource', message: NO_EVENT_SOURCE }],
      'no-restricted-properties': ['error',
        ...['window', 'globalThis', 'self'].map((object) => ({ object, property: 'EventSource', message: NO_EVENT_SOURCE }))],
      'no-restricted-imports': restrictedImports(),
    },
  },
  {
    // 端到端测试的 test 必须来自 e2e/support/test（带自动的外网拦截）
    files: ['e2e/**/*.ts'],
    ignores: ['e2e/support/test.ts'],
    rules: {
      'no-restricted-imports': restrictedImports([{
        name: '@playwright/test',
        importNames: ['test'],
        message: '从 e2e/support/test 引入 test：它会自动拦截外网请求',
      }]),
    },
  },
  {
    files: ['**/*.{js,mjs,cjs}'],
    ...tseslint.configs.disableTypeChecked,
    languageOptions: { ...tseslint.configs.disableTypeChecked.languageOptions, globals: globals.node },
  },
)
