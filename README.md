# good-life

个人档案驱动的健康生活智能体。当前完成的是步骤 01：项目底座与账号档案（后端服务、PostgreSQL、注册登录、个人档案、免责声明）。

定位声明：只提供生活方式建议，不做医疗诊断，不替代医生。

本文所有命令按 Windows 11 加 PowerShell 5.1 编写。PowerShell 5.1 不支持 `&&`，多条命令请分行逐条执行。

## 1. 前置条件

- Docker Desktop（需要已启动，用来运行 PostgreSQL 16）
- Python 3.12
- uv（Python 包与虚拟环境管理工具）

先确认三者都可用：

```powershell
docker --version
python --version
uv --version
```

## 2. 启动数据库

在仓库根目录执行：

```powershell
docker compose up -d --wait db
```

数据库映射到本机 5433 端口，账号、密码、库名都是 `goodlife`。首次创建数据卷时，`deploy/db-init` 下的脚本会自动再建一个测试库 `goodlife_test`。

## 3. 安装依赖

```powershell
cd backend
uv sync
```

`uv sync` 会创建 `backend/.venv` 并安装运行依赖与开发依赖（测试用的 HTTP 客户端依赖是 `httpx2`，不是 `httpx`）。后面的命令都在 `backend` 目录下执行，并统一用 `uv run` 开头。

## 4. 配置

把示例配置复制为 `backend/.env`：

```powershell
Copy-Item .env.example .env
```

生成两个密钥：

```powershell
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

第一条的输出填到 `.env` 的 `JWT_SECRET`，第二条的输出填到 `FIELD_ENCRYPTION_KEY`。`DATABASE_URL` 与 `ACCESS_TOKEN_EXPIRE_MINUTES`（登录令牌有效分钟数，默认 10080，即 7 天）保持示例值即可。

重要：

- `backend/.env` 含密钥，绝对不能提交到仓库（已在 `.gitignore` 中忽略）。仓库里只保留 `.env.example`。
- `FIELD_ENCRYPTION_KEY` 用来加密档案中的身高、体重、健康状况、备注和修改记录。这个密钥一旦丢失或更换，已经加密的数据就无法再解密，请自行妥善备份。
- `JWT_SECRET` 更换后，所有已签发的登录令牌立即失效，用户需要重新登录。

## 5. 建表

```powershell
uv run alembic upgrade head
```

该命令按迁移脚本在开发库 `goodlife` 中创建 `users`、`disclaimer_acceptances`、`profiles`、`profile_changes` 四张表。

## 6. 运行测试

```powershell
uv run pytest -v
```

测试固定连接 `goodlife_test` 库并使用测试专用密钥，不会读取 `.env` 里的密钥，也不会影响开发库。测试库的表由测试自己迁移创建，每个测试结束后自动清空。

## 7. 启动服务

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

- 接口文档（Swagger）：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health ，正常返回 `{"status":"ok"}`

## 8. 手动体验顺序

打开 http://localhost:8000/docs，按下面顺序操作：

1. 注册：`POST /api/auth/register`，点 Try it out，填 `username`（3 到 32 位，只能是字母、数字、下划线，不区分大小写）和 `password`（8 到 128 位），执行。重复注册同一用户名会返回 409 和 `username_taken`。
2. 登录：`POST /api/auth/login`，填同样的账号密码，从返回内容里复制 `access_token`。
3. 授权：点页面右上角的 Authorize 按钮，把令牌填进 Value 框（只填令牌本身，不要加 `Bearer ` 前缀），点 Authorize 后关闭弹窗。此后所有请求会自动带上令牌。
4. 确认免责声明：先 `GET /api/disclaimer` 查看当前版本号和正文，再 `POST /api/disclaimer/accept`，把返回的版本号填进 `version` 后执行。未确认前，读写档案会返回 403 和 `disclaimer_not_accepted`。
5. 读写档案：`GET /api/profile` 读取（新用户是空档案）；`PATCH /api/profile` 只填想修改的字段，例如 `{"goal": "maintain", "height_cm": 172.5}`；再读一次得到新值；`GET /api/profile/changes` 查看修改记录；`GET /api/me/capabilities` 查看哪些后续模块对你开放。
6. 退出：`POST /api/auth/logout`。退出后这个令牌立即失效，再用它访问会返回 401。

## 9. 常见问题

**5433 端口被占用，数据库起不来。** 同时修改两处，缺一不可：

1. 仓库根目录 `docker-compose.yml` 中 `ports` 一行，把 `"5433:5432"` 冒号左边改成空闲端口，例如 `"5434:5432"`。
2. `backend/.env` 中 `DATABASE_URL` 的端口改成同一个数字。

测试默认也连 5433；改了端口后，先在当前 PowerShell 窗口设置环境变量再跑测试：

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://goodlife:goodlife@localhost:5434/goodlife_test"
uv run pytest -v
```

**测试报错找不到 `goodlife_test` 库。** 说明数据卷是在加入 `deploy/db-init` 初始化脚本之前就创建的，脚本只在数据卷首次创建时执行。在仓库根目录删掉旧数据卷重建（会清空开发库里的全部数据）：

```powershell
docker compose down -v
docker compose up -d --wait db
cd backend
uv run alembic upgrade head
```

**8000 端口被占用。** 把启动命令里的 `--port 8000` 换成其他端口，文档地址随之改变。

**启动时报缺少配置项。** 确认 `backend/.env` 存在、三项必填配置（`DATABASE_URL`、`JWT_SECRET`、`FIELD_ENCRYPTION_KEY`）都已填写。

**启动时报密钥不合法（占位值、`JWT_SECRET` 至少需要 32 个字符、不是有效的 Fernet 密钥）。** 服务启动时会校验两个密钥，仍是 `.env.example` 里以 `replace-with` 开头的占位值、`JWT_SECRET` 不足 32 个字符、`FIELD_ENCRYPTION_KEY` 不是有效的 Fernet 密钥都会直接拒绝启动。按第 4 节重新生成两个密钥填入 `backend/.env` 即可。
