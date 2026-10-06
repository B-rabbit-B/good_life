# good-life

个人档案驱动的健康生活智能体。当前完成的是步骤 01（项目底座与账号档案：后端服务、PostgreSQL、注册登录、个人档案、免责声明）、步骤 02（经期模块：经期记录、统计、预测、阶段判断与阶段提示）和步骤 03（医嘱模块：医嘱录入与提取、条目确认、状态流转、当前约束查询、解除与审计、证据文件）。步骤 01 至 03 已验收通过。步骤 04（营养与饮食约束引擎：营养库与检索、饮食记录与每日汇总、需求估算、融合医嘱、经期、目标与当日摄入的饮食判断）已完成开发，待验收。

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

数据库映射到本机 5433 端口（只监听 127.0.0.1，局域网内其他机器连不上），账号、密码、库名都是 `goodlife`。首次创建数据卷时，`deploy/db-init` 下的脚本会自动再建一个测试库 `goodlife_test`。

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
- `FIELD_ENCRYPTION_KEY` 用来加密档案中的身高、体重、健康状况、备注和修改记录，以及经期模块的每日记录内容和经期状态，医嘱模块的医嘱原文、条目内容、审计详情、证据文件名与文件内容，饮食模块的饮食记录备注。这个密钥一旦丢失或更换，已经加密的数据就无法再解密，请自行妥善备份。
- `JWT_SECRET` 更换后，所有已签发的登录令牌立即失效，用户需要重新登录。

## 5. 建表

```powershell
uv run alembic upgrade head
```

该命令按迁移脚本在开发库 `goodlife` 中创建 `users`、`disclaimer_acceptances`、`profiles`、`profile_changes`（步骤 01）和 `cycle_periods`、`cycle_day_logs`、`cycle_settings`（步骤 02 经期模块）以及 `medical_orders`、`medical_evidence`、`medical_items`、`medical_item_events`（步骤 03 医嘱模块）以及 `meal_entries`（步骤 04 饮食记录）共十二张表。营养库不入数据库，随程序从数据文件加载。

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

1. 仓库根目录 `docker-compose.yml` 中 `ports` 一行，把 `"127.0.0.1:5433:5432"` 中间的 5433 改成空闲端口，例如 `"127.0.0.1:5434:5432"`。
2. `backend/.env` 中 `DATABASE_URL` 的端口改成同一个数字。

测试默认也连 5433；改了端口后，先在当前 PowerShell 窗口设置环境变量再跑测试：

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://goodlife:goodlife@127.0.0.1:5434/goodlife_test"
uv run pytest -v
```

**测试报错找不到 `goodlife_test` 库。** 说明数据卷是在加入 `deploy/db-init` 初始化脚本之前就创建的，脚本只在数据卷首次创建时执行。在仓库根目录删掉旧数据卷重建（会清空开发库里的全部数据）：

```powershell
docker compose down -v
docker compose up -d --wait db
cd backend
uv run alembic upgrade head
```

**连接数据库很慢或超时。** 数据库只监听 127.0.0.1；`DATABASE_URL` 里如果写的是 `localhost`，Windows 会先尝试 IPv6 地址而卡住很久。把 `backend/.env` 中的 `localhost` 改成 `127.0.0.1` 即可（`.env.example` 已是这样）。

**8000 端口被占用。** 把启动命令里的 `--port 8000` 换成其他端口，文档地址随之改变。

**启动时报缺少配置项。** 确认 `backend/.env` 存在、三项必填配置（`DATABASE_URL`、`JWT_SECRET`、`FIELD_ENCRYPTION_KEY`）都已填写。

**启动时报密钥不合法（占位值、`JWT_SECRET` 至少需要 32 个字符、不是有效的 Fernet 密钥）。** 服务启动时会校验两个密钥，仍是 `.env.example` 里以 `replace-with` 开头的占位值、`JWT_SECRET` 不足 32 个字符、`FIELD_ENCRYPTION_KEY` 不是有效的 Fernet 密钥都会直接拒绝启动。按第 4 节重新生成两个密钥填入 `backend/.env` 即可。

## 10. 经期模块演示

经期功能只对档案性别为女性、且没有关闭该功能的用户开放；其他用户访问 `/api/cycle` 开头的接口会得到 403 和 `cycle_not_available`。仅供参考，经期预测与阶段提示不能用于避孕或诊断。

先确认开发库已建到最新版本（包含经期的三张表），再创建演示账号，都在 `backend` 目录下执行：

```powershell
uv run alembic upgrade head
uv run python -m app.cycle.demo
```

脚本会创建三个演示账号，密码都是 `demo-pass-123`，它们已经确认免责声明并把档案性别设为女性：

| 用户名 | 类型 | 特点 |
|---|---|---|
| `demo_regular` | 规律型 | 4 个周期，长度 28、28、29、28 天；预测区间窄，没有降级标记 |
| `demo_irregular` | 波动型 | 5 个周期，长度 24、33、27、36、31 天；预测区间明显更宽，带 `irregular`（近几次周期长短差异较大）等标记 |
| `demo_sparse` | 数据不足型 | 只有 2 次月经；预测显示“数据不足”，不给出日期 |

脚本可以重复运行：已存在的账号会被跳过，输出“演示账号已存在，未重复创建。”。月经记录以运行当天为基准倒推，最近一次月经从今天往前 10 天开始，所以隔几天再看，“今天”离最近一次月经越来越远，出现 `overdue`（已经超过预计的月经开始时间）标记属于正常现象。

启动服务后，在接口文档页面（http://localhost:8000/docs）按下面顺序体验，登录与授权的操作同第 8 节：

1. 登录：`POST /api/auth/login`，用 `demo_regular` 和 `demo-pass-123` 登录，把令牌填进 Authorize。
2. 查看经期记录：`GET /api/cycle/periods`，应看到 5 次月经，从新到旧排列。
3. 查看统计：`GET /api/cycle/stats`，规律型应是平均周期 28.3 天、波动 0.5、平均经期 5.0 天。
4. 查看预测：`GET /api/cycle/prediction`，看预计下次月经、排卵日、易孕窗口和区间，末尾有“仅供参考，不能用于避孕或诊断”的说明。换 `demo_irregular` 和 `demo_sparse` 登录，对比区间宽度与“数据不足”。
5. 查看今天的阶段与提示：`GET /api/cycle/phase` 和 `GET /api/cycle/tips`，不填日期就是今天；也可以填 `date` 查任意一天。
6. 切换孕期状态：`PUT /api/cycle/settings`，提交 `{"status": "pregnant"}`，再看 `GET /api/cycle/prediction`，状态变为已暂停且没有日期；查阶段则显示未知。改回 `{"status": "tracking"}` 后预测恢复。
7. 想让自己注册的账号也能用：`PATCH /api/profile` 把 `gender` 设为 `female`，再访问经期接口。

完整的表结构、算法、接口、样例与验收记录见 `docs/02-交付物/`。

## 11. 医嘱模块演示

医嘱功能对任何性别开放，只要已登录并确认免责声明即可使用，访问 `/api/medical` 开头的接口。医嘱提取结果仅供参考，全部需要你确认才生效；系统不判断药物剂量与药物相互作用，请遵医嘱或咨询医生、药师。

先确认开发库已建到最新版本（包含医嘱的四张表），再创建演示账号，都在 `backend` 目录下执行：

```powershell
uv run alembic upgrade head
uv run python -m app.medical.demo
```

脚本会创建演示账号 `demo_medical`，密码是 `demo-pass-123`，它已经确认免责声明，名下录入了三份样例医嘱（短期忌口、长期慢病饮食、带复查日的术后饮食限制），共 9 条条目，全部处于待确认状态。脚本可以重复运行：账号已存在时输出“演示账号已存在，未重复创建。”，不会重复写入。

启动服务后，在接口文档页面（http://localhost:8000/docs）按下面顺序体验，登录与授权的操作同第 8 节：

1. 登录：`POST /api/auth/login`，用 `demo_medical` 和 `demo-pass-123` 登录，把令牌填进 Authorize。
2. 查看医嘱与待确认条目：`GET /api/medical/orders` 看三份医嘱的原文、被忽略的句子与原因；`GET /api/medical/items`，`status` 填 `pending_confirmation`，应有 9 条。此时 `GET /api/medical/constraints` 是空的，未确认的条目不算约束。
3. 修改并确认一条：挑一条饮食禁忌，`POST /api/medical/items/{item_id}/confirm`，正文里可以一并修改，例如 `{"subjects": ["辛辣", "油腻", "酒", "咖啡"]}`；返回状态变为 `active`。
4. 查看当前约束：`GET /api/medical/constraints`，能看到刚确认的这一条，末尾有“请遵医嘱”的提醒；用 `category` 可以按类别筛选。
5. 上传一张医嘱图片并下载核对：`POST /api/medical/orders/{order_id}/evidence` 选择一张 JPG、PNG、WEBP 图片或 PDF（不超过 10 MB）；再 `GET /api/medical/evidence/{evidence_id}` 下载，核对内容一致。
6. 提出解除建议：`POST /api/medical/items/{item_id}/propose-resolution`，填 `{"reason": "复诊一切正常"}`；再查一次当前约束，这一条仍然在，只是带有待处理的解除建议标记。
7. 确认解除：`POST /api/medical/items/{item_id}/resolve`，状态变为 `resolved`；当前约束里不再有它，但 `GET /api/medical/items` 用 `status` 填 `resolved` 仍能查到。
8. 查看审计记录：`GET /api/medical/items/{item_id}/events`，按顺序看到创建、确认、提出解除建议、确认解除四条记录，各有时间、来源和详情。

演示数据与日期有关：三份样例以运行脚本那天为开具日期。以 9 月 30 日运行为例，短期样例里“清淡、流质、半流质”一条的预计结束日期是 10 月 2 日，一直不确认的话从 10 月 3 日（运行后第 3 天）起会被自动作废；“忌食辛辣……禁酒”一条的预计结束日期是 10 月 6 日，确认后从 10 月 5 日（运行当天算第 1 天的第 6 天）起进入待复核。所以请在体验前不久再运行演示脚本；如果演示账号是几天前创建的，看到的条目数量和状态会与上面描述不同，请在数据库里删除用户名为 `demo_medical` 的账号（名下的医嘱、条目和记录会随之删除）后重新运行脚本。

到期自动转待复核依赖“今天”的日期，接口文档页面无法调整，请用自动化测试核对（见验收记录）。想让自己注册的账号使用医嘱功能，登录并确认免责声明后直接访问即可。

完整的表结构、状态流转、提取规则、接口、样例评测与验收记录见 `docs/03-交付物/`。

## 12. 饮食与约束引擎演示

饮食功能对任何性别开放，只要已登录并确认免责声明即可使用，访问 `/api/nutrition` 开头的接口。判断结果与估算的每日需求仅供参考，不构成医疗建议，有医嘱时以医嘱为准；营养库里的成分表整理数据仅供个人学习，商用前必须核实授权。

先确认开发库已建到最新版本（包含饮食记录表），再创建演示账号，都在 `backend` 目录下执行：

```powershell
uv run alembic upgrade head
uv run python -m app.nutrition.demo
```

脚本会创建四个演示账号，密码都是 `demo-pass-123`，都已确认免责声明并填好完整档案：

| 用户名 | 类型 | 特点 |
|---|---|---|
| `demo_avoid` | 有忌口医嘱 | 已确认一条医嘱“一周内忌食辛辣、油腻食物，禁酒” |
| `demo_period` | 经期 | 4 次月经，最近一次从昨天开始、尚未结束，今天是月经期 |
| `demo_muscle` | 增肌 | 目标增肌，没有医嘱 |
| `demo_healthy` | 健康无约束 | 目标维持，没有医嘱，没有经期规则 |

脚本可以重复运行：已存在的账号会被跳过，输出“演示账号已存在，未重复创建。”。月经与医嘱都以运行当天为基准，所以请在体验前不久运行；账号建好很久以后，医嘱可能已经到期转待复核（仍按原要求执行），想恢复原样，在数据库里删除对应用户名的账号（名下的数据会随之删除）后重新运行脚本。

启动服务后，在接口文档页面（http://localhost:8000/docs）按下面顺序体验，登录与授权的操作同第 8 节：

1. 登录：`POST /api/auth/login`，先用 `demo_healthy` 和 `demo-pass-123` 登录，把令牌填进 Authorize。
2. 体验检索：`GET /api/nutrition/foods/search`，q 填 `米饭`、`西红柿炒鸡蛋`、`宫保鸡丁` 等，看命中的食物与命中方式；再填 `酸菜鱼` 这类库里没有、只有相近名称的词，返回的 `exact` 为假并提示请确认候选；再填一个不存在的词，返回“未找到”的明确提示。`GET /api/nutrition/foods/{food_id}` 查看营养、标签、份量和来源（出处与授权状态）。
3. 记录三餐看汇总：`POST /api/nutrition/meals`，`eaten_on` 填今天，`meal_type` 选早餐、午餐、晚餐，`food_id` 填检索得到的编号，`grams` 或 `portion` 二选一；记录几次后 `GET /api/nutrition/summary` 看每餐与全天合计、估算的需求与剩余额度，与手算对照；`GET /api/nutrition/needs` 单独看估算的需求。
4. 判断同一个食物：`POST /api/nutrition/evaluate`，填同一个 `food_id`（例如麻婆豆腐、西瓜、啤酒、猪肝、鸡胸肉），依次换 `demo_avoid`、`demo_period`、`demo_muscle`、`demo_healthy` 登录（重新授权），比较四个账号的结论与依据：忌口账号对麻婆豆腐、啤酒得到“不建议”并指出是哪条医嘱；经期账号对西瓜得到“谨慎”，依据来自经期提示（传统经验，不是医嘱）；增肌账号对鸡胸肉得到健身目标的正面依据；健康账号对常见食物都是“适合”。
5. 判断一整餐：`POST /api/nutrition/evaluate-meal`，`items` 里放几个食物，看每一项和整餐的结论。
6. 看标签：`GET /api/nutrition/tags` 查看全部标签及类别，寒凉、温热是传统经验，不是医学结论。

判断只针对今天，接口没有日期参数；到期转待复核需要改变“今天”，请用自动化测试核对（见验收记录）。想让自己注册的账号体验：登录并确认免责声明后直接访问即可，档案里填好出生年份、身高、体重、活动水平后才有估算的需求，经期规则需要把 `gender` 设为 `female` 并录入月经。

完整的数据来源与授权、标签审核表、约束融合规则、接口、验证场景与验收记录见 `docs/04-交付物/`。
