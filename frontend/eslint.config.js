import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'
import tseslint from 'typescript-eslint'

const ANIMATION_LIBRARIES = ['framer-motion', 'motion', 'gsap', 'react-spring', 'animejs']

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
      'no-restricted-globals': ['error', { name: 'EventSource', message: '用 src/api/sse.ts' }],
      'no-restricted-imports': ['error', {
        paths: ANIMATION_LIBRARIES.map((name) => ({ name, message: '不引入动画库：动效只用 CSS 与 Web Animations API' })),
        patterns: [
          { group: ['@react-spring/*', ...ANIMATION_LIBRARIES.map((name) => `${name}/*`)],
            message: '不引入动画库：动效只用 CSS 与 Web Animations API' },
        ],
      }],
    },
  },
  {
    files: ['**/*.{js,mjs,cjs}'],
    ...tseslint.configs.disableTypeChecked,
    languageOptions: { ...tseslint.configs.disableTypeChecked.languageOptions, globals: globals.node },
  },
)
