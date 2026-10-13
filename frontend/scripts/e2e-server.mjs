// Playwright 的 webServer：先构建端到端用的前端（dist-e2e），再在后端目录启动 app.e2e_server（测试库加本地模拟服务）。
// 子进程的输出原样转发；收到退出信号时连同子进程一起结束。
import { spawn, spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = fileURLToPath(new URL('..', import.meta.url))
const backend = join(frontend, '..', 'backend')
const windows = process.platform === 'win32'

const build = spawnSync('pnpm', ['build:e2e'], { cwd: frontend, stdio: 'inherit', shell: windows })
if (build.error) throw build.error
if (build.status !== 0) process.exit(build.status ?? 1)

const server = spawn(
  'uv',
  ['run', 'python', '-m', 'app.e2e_server', '--port', '8765', '--dist', '../frontend/dist-e2e',
    '--fixtures', '../frontend/e2e/.fixtures'],
  { cwd: backend, stdio: 'inherit', env: { ...process.env, PYTHONUTF8: '1' } },
)

function stop() {
  if (server.exitCode !== null || server.pid === undefined) return
  if (windows) {
    // uv 会再起一个 python 子进程，Windows 上要按进程树结束
    spawnSync('taskkill', ['/pid', String(server.pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    server.kill('SIGTERM')
  }
}

for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
  process.on(signal, () => {
    stop()
    process.exit(0)
  })
}
process.on('exit', stop)
server.on('exit', (code, signal) => process.exit(code ?? (signal ? 1 : 0)))
