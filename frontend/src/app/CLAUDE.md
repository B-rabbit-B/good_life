# frontend/src/app 目录说明书

## 职责
- 把各层装起来：App.tsx（查询客户端、磨砂模式、遮盖、轻提示、路由）、routes.tsx（路由表，页面一律按需加载）、guards.tsx（路由守卫）、AppShell.tsx（外壳：唯一的滚动容器、底部导航、对话底座与操作坞的留白、敏感页登记）。
- 守卫的判断全部来自后端：未登录 → 登录页；未确认免责（或免责换了版本，档案或能力清单回 403 disclaimer_not_accepted）→ 免责页；档案未填完 → 建档页；模块未开放 → 对话页。
- sensitiveAreas.ts 是“本页有敏感区”的登记表（DESIGN.md 第四节），也提供核对函数；它不依赖 React 与浏览器，端到端测试直接引入。
- nav.ts 只按能力清单决定导航项；paths.ts 是全部路径；queryClient.ts 只对 5xx 与网络错误重试一次，并且离线时也真的发请求（NETWORK_MODE always）。

## 边界
- 可以引用 lib、api、components、features 与 dev（只在开发模式或 VITE_GALLERY=1 时注册样张页）。
- components 只能引用这里的 shellContext 与 sensitiveAreas（test/boundaries.test.ts 的登记例外）；features 引用 paths、AppShell 的登记钩子、nav、guards 等。
- profile.ts 的“建档是否填完”是流程判断（后端没有这个字段），不是业务规则。

## 入口
- 新页面：在 routes.tsx 加按需加载的路由与 handle（导航、外壳形态、敏感页键），路径加进 paths.ts；有敏感内容就在 sensitiveAreas.ts 登记区域名，并在页面里调用登记钩子。
- 测试：AppShell.test.tsx、guards.test.tsx、routes.test.tsx、nav.test.ts、profile.test.ts、queryClient.test.ts。

## 禁区
- 不在守卫或导航里自己推断模块是否开放（例如按性别判断经期），只看 /api/me/capabilities。
- 不静态引入页面组件：页面静态引入会进入首屏块，破坏首屏预算；对话页是首屏，它带进来的东西要很小。
- 改 SENSITIVE_AREAS 要同步页面上的 Sensitive 区域名与端到端核对，两边不一致测试会失败。
- 退出与会话失效统一走 useLogout 与 client 的 401 通知，清令牌并清空查询缓存，不留上一个用户的数据。
