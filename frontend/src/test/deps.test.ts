// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

interface PackageJson {
  license?: string
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
}

const root = new URL('../../', import.meta.url)
const readPackage = (path: string) => JSON.parse(readFileSync(new URL(path, root), 'utf8')) as PackageJson

const ALLOWED_LICENSES = ['MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause']
const ANIMATION_LIBRARIES = ['framer-motion', 'motion', 'gsap', 'react-spring', 'animejs', 'react-bits']

// 每个直接依赖的许可证都登记在这里；新增依赖时先核对许可证再登记
const RECORDED_LICENSES: Record<string, string> = {
  '@internationalized/date': 'Apache-2.0',
  '@tanstack/react-query': 'MIT',
  react: 'MIT',
  'react-aria-components': 'Apache-2.0',
  'react-dom': 'MIT',
  'react-router': 'MIT',
  '@eslint/js': 'MIT',
  '@playwright/test': 'Apache-2.0',
  '@testing-library/jest-dom': 'MIT',
  '@testing-library/react': 'MIT',
  '@testing-library/user-event': 'MIT',
  '@types/node': 'MIT',
  '@types/react': 'MIT',
  '@types/react-dom': 'MIT',
  '@vitejs/plugin-basic-ssl': 'MIT',
  '@vitejs/plugin-react': 'MIT',
  eslint: 'MIT',
  'eslint-plugin-react-hooks': 'MIT',
  globals: 'MIT',
  jsdom: 'MIT',
  msw: 'MIT',
  'openapi-typescript': 'MIT',
  typescript: 'Apache-2.0',
  'typescript-eslint': 'MIT',
  vite: 'MIT',
  vitest: 'MIT',
}

const own = readPackage('package.json')
const direct = [...Object.keys(own.dependencies ?? {}), ...Object.keys(own.devDependencies ?? {})].sort()

describe('dependencies', () => {
  it('every direct dependency has an allowed license', () => {
    expect(direct).toEqual(Object.keys(RECORDED_LICENSES).sort())
    const installed = Object.fromEntries(
      direct.map((name) => [name, readPackage(`node_modules/${name}/package.json`).license ?? '（未声明）']),
    )
    expect(installed).toEqual(RECORDED_LICENSES)
    const rejected = Object.entries(installed).filter(([, license]) => !ALLOWED_LICENSES.includes(license))
    expect(rejected).toEqual([])
  })

  it('no animation library is installed', () => {
    const banned = direct.filter((name) => ANIMATION_LIBRARIES.includes(name) || name.startsWith('@react-spring/'))
    expect(banned).toEqual([])
    // 间接依赖也不行：pnpm 把每个安装的包放在 node_modules/.pnpm/<名字>@<版本>（作用域里的斜杠写成 +）
    const store = readdirSync(new URL('node_modules/.pnpm/', root))
    const transitive = store.filter((entry) =>
      entry.startsWith('@react-spring+') || ANIMATION_LIBRARIES.some((name) => entry.startsWith(`${name}@`)))
    expect(transitive).toEqual([])
  })
})
