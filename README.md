# good-life

个人档案驱动的健康生活智能体。当前完成的是步骤 01（项目底座与账号档案：后端服务、PostgreSQL、注册登录、个人档案、免责声明）、步骤 02（经期模块：经期记录、统计、预测、阶段判断与阶段提示）和步骤 03（医嘱模块：医嘱录入与提取、条目确认、状态流转、当前约束查询、解除与审计、证据文件）。此外还完成了步骤 04（营养与饮食约束引擎：营养库与检索、饮食记录与每日汇总、需求估算、融合医嘱、经期、目标与当日摄入的饮食判断）。随后完成了步骤 05（健身模块：内置动作库与自定义动作、训练记录、周汇总与动作趋势、能量消耗估算、训练信号与饮食联动、运动限制冲突提示）。随后完成了步骤 06（SDK 与 MCP：进程内 SDK 封装前面各模块的能力，用户可签发只读或读写的智能体授权，再通过本地 MCP 服务让任何支持 MCP 的客户端调用，医嘱确认与解除不暴露给模型，每次调用留审计）。步骤 01 至 06 均已验收通过。步骤 07（多模型接入：用户填写模型服务的地址与密钥，由后端拉取模型列表、标注看图与工具调用能力、测试连通性、为日常对话与看图识别分别选择模型，并用统一的方式调用 Claude、Gemini 与各种兼容格式的服务，密钥加密保存、只显示掩码）已有条件通过：除真实服务实测外的 6 条验收标准已代验通过，真实服务实测需要你本人运行实测脚本补做，见第 16 节。步骤 08（智能体层：会聊天、会按档案调用工具、按规则主动开场提问的站内智能体，回答发出前由输出检查保证不提到医嘱禁忌的食物，涉及用药、严重症状、孕期异常、极端节食与自伤的话题只给固定的安全回复，依据只来自步骤 04 的引擎）已有条件通过：第 3 至 8 条已代验通过，第 1、2、9 条的真实模型表现还需要你用真实模型运行智能体实测脚本补做，见第 17 节。步骤 09（拍照识别：上传一张饭菜照片，由“看图识别”用途的模型认出菜品与份量，匹配营养库按克数算出热量与营养并给出数据出处，匹配不上的标为待确认，用户可以修正，确认后才写入饮食记录，并由步骤 04 的引擎按个人约束评价这一餐；原图默认不保留）已有条件通过：第 2 至 7 条已代验通过，第 1、9 条的流程与规则部分已代验；第 8 条需要你用至少二十张自选照片运行照片评测脚本，第 1、9 条的真实模型表现也由这次评测给出，见第 19 节。步骤 10（附近餐厅推荐：不想做饭时，按授权的定位或手动输入的地点，用高德检索附近的餐饮场所，按步骤 04 的引擎结合医嘱、目标与当日摄入判断每类餐厅适不适合，避开命中忌口的类型并说明原因，给出“到店可点什么、应避开什么”的一般性建议与地图导航链接；精确位置不入库，只在用户选择时保存可清除的粗略区域）已有条件通过：第 3 至 7 条已代验通过，第 1、2 条的流程与规则部分已代验；第 1、2 条的真实检索需要你在服务端配置高德密钥后运行实测脚本，见第 20 节。第二阶段（步骤 07 至 10）整体验收已有条件通过：在本机的模拟模型与模拟高德下，聊天、拍照识别、主动开场、餐厅推荐已通过接口完整走通；真实模型与真实高德的实测仍需你本人补做，见第 21 节。

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

`uv sync` 会创建 `backend/.venv` 并安装运行依赖与开发依赖（HTTP 客户端依赖是 `httpx2`，不是 `httpx`；后端用它调用模型服务，测试也用它）。后面的命令都在 `backend` 目录下执行，并统一用 `uv run` 开头。

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

第一条的输出填到 `.env` 的 `JWT_SECRET`，第二条的输出填到 `FIELD_ENCRYPTION_KEY`。`DATABASE_URL` 与 `ACCESS_TOKEN_EXPIRE_MINUTES`（登录令牌有效分钟数，默认 10080，即 7 天）保持示例值即可。`AMAP_KEY`、`AMAP_BASE_URL`、`AMAP_TIMEOUT_SECONDS` 是附近餐厅推荐用的高德配置，`AMAP_KEY` 可以先留空（附近餐厅功能关闭），见第 20 节。

重要：

- `backend/.env` 含密钥，绝对不能提交到仓库（已在 `.gitignore` 中忽略）。仓库里只保留 `.env.example`。
- `FIELD_ENCRYPTION_KEY` 用来加密档案中的身高、体重、健康状况、备注和修改记录，以及经期模块的每日记录内容和经期状态，医嘱模块的医嘱原文、条目内容、审计详情、证据文件名与文件内容，饮食模块的饮食记录备注，健身模块的训练备注。这个密钥一旦丢失或更换，已经加密的数据就无法再解密，请自行妥善备份。
- `JWT_SECRET` 更换后，所有已签发的登录令牌立即失效，用户需要重新登录。

## 5. 建表

```powershell
uv run alembic upgrade head
```

该命令按迁移脚本在开发库 `goodlife` 中创建 `users`、`disclaimer_acceptances`、`profiles`、`profile_changes`（步骤 01）和 `cycle_periods`、`cycle_day_logs`、`cycle_settings`（步骤 02 经期模块）以及 `medical_orders`、`medical_evidence`、`medical_items`、`medical_item_events`（步骤 03 医嘱模块）以及 `meal_entries`（步骤 04 饮食记录）以及 `custom_exercises`、`workouts`、`strength_sets`、`cardio_entries`（步骤 05 健身模块）以及 `agent_grants`、`sdk_call_audits`（步骤 06 的智能体授权与调用审计）以及 `llm_providers`、`llm_models`、`llm_assignments`（步骤 07 的模型服务、模型与用途分配）以及 `agent_conversations`、`agent_messages`、`agent_preferences`、`agent_openings`、`agent_settings`（步骤 08 的智能体会话、消息、偏好、开场记录与设置）以及 `photo_recognitions`（步骤 09 的拍照识别记录）以及 `restaurant_settings`（步骤 10 的附近餐厅设置）共二十八张表。营养库与内置动作库都不入数据库，随程序从数据文件加载。

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

## 13. 健身模块演示

健身功能对任何性别开放，只要已登录并确认免责声明即可使用，访问 `/api/fitness` 开头的接口。能量消耗只是估算，给出区间并标注“仅为估算”；运动限制的冲突提示只提示、不阻止记录，也不替代医生的意见。

先确认开发库已建到最新版本（包含健身的四张表），再创建演示账号，都在 `backend` 目录下执行：

```powershell
uv run alembic upgrade head
uv run python -m app.fitness.demo
```

脚本会创建演示账号 `demo_fitness`，密码是 `demo-pass-123`，它已经确认免责声明，档案是一位男性增肌用户（体重 70 千克，档案完整）。名下有一个自定义动作“史密斯机划船”和一周的训练记录（以运行当天为第七天往前倒推，下面把这七天称为周一到周日，今天是周日，不是日历上的星期几）：

| 称呼 | 内容 |
|---|---|
| 周一（6 天前） | 胸与三头：卧推 60 千克、哑铃飞鸟、绳索下压 |
| 周二 | 跑步 30 分钟 |
| 周三 | 背与二头：引体向上、杠铃划船、自定义的史密斯机划船、哑铃弯举 |
| 周四 | 休息日，没有记录 |
| 周五 | 腿：深蹲、腿举、提踵 |
| 周六 | 游泳 40 分钟 |
| 周日（今天） | 卧推 65 千克（比周一重）、哑铃卧推 |

脚本可以重复运行：账号已存在时输出“演示账号已存在，未重复创建。”，不会重复写入。想恢复原样，在数据库里删除用户名为 `demo_fitness` 的账号（名下的训练与自定义动作会随之删除）后重新运行脚本。训练日期以运行当天为基准，所以请在体验前不久运行。

启动服务后，在接口文档页面（http://localhost:8000/docs）按下面顺序体验，登录与授权的操作同第 8 节：

1. 登录：`POST /api/auth/login`，用 `demo_fitness` 和 `demo-pass-123` 登录，把令牌填进 Authorize。
2. 检索动作：`GET /api/fitness/exercises/search`，q 填 `卧推`、`杠铃推举`（别名，对应站姿推举）、`跑步`，再填 `史密斯划船`（只有本人看得到的自定义动作）和一个不存在的词（返回“未找到”并提示可以新增自定义动作）；`GET /api/fitness/exercises/{exercise_id}` 查看肌群、器械和三档代谢当量（编号形如 `ex:running`）。
3. 看训练记录：`GET /api/fitness/workouts`，默认是最近 7 天，日期新的在前，应有 6 条；`GET /api/fitness/workouts/{workout_id}` 看单条，里面的 `conflicts` 是与医嘱运动限制的冲突提示，演示账号没有医嘱，所以是空的。
4. 记录一次训练：`POST /api/fitness/workouts`，例如日期填今天，`strength` 里放卧推三组（60 千克 10 次、60 千克 8 次、65 千克 6 次），手算训练量是 600 加 480 加 390 等于 1470；`PUT /api/fitness/workouts/{workout_id}` 可以整条替换（补录和修改都用它）。日期晚于今天会被拒绝。
5. 看汇总与趋势：`GET /api/fitness/summary/week`，`start` 必须是星期一，不填就是本周；核对总训练量、各肌群训练量与能量消耗区间，区间下方有“仅为估算”的说明。`GET /api/fitness/exercises/ex:bench_press/trend` 看卧推趋势，应有两个点：最高重量 60 到 65 千克，训练量 1440 到 1560。
6. 看今天的训练信号：`GET /api/fitness/signal`，应是训练、力量、高强度，估算区间 81 至 122 千卡，涉及肌群是胸、肩、肱三头肌。
7. 看对饮食的影响：`GET /api/nutrition/needs`，能量需求比不训练时多 81 千卡，说明里写明“已计入当天训练估算消耗的下限 81 千卡。”；`POST /api/nutrition/evaluate` 判断米饭与鸡胸肉（食物编号用 `GET /api/nutrition/foods/search` 取得），依据里出现训练来源：米饭有“快碳”推荐，鸡胸肉有“高蛋白”推荐，两者都说明了能量额度加了多少。另注册一个同样档案、今天没有训练的账号对比：没有训练依据，能量需求也不加。
8. 体验运动限制的冲突：另注册一个账号并确认免责声明，用 `POST /api/medical/orders` 录入“两周内避免提重物及剧烈运动。”，再 `POST /api/medical/items/{item_id}/confirm` 确认其中的运动限制条目；记录一次卧推，返回的 `conflicts` 里会提示涉及“提重物”，训练照样保存；`GET /api/fitness/signal` 与饮食判断的依据里也有对应提示。把这次训练整条替换成快走，冲突消失。

训练日期与“今天”有关，接口文档页面无法调整“今天”，休息日与不同日期的对比请用自动化测试核对（见验收记录）。

完整的表结构、口径、联动规则、接口、演示样例与验收记录见 `docs/05-交付物/`。

## 14. SDK 与 MCP 演示

步骤 06 把前面各模块的能力整理成一份进程内 SDK，再用一个本地 MCP 服务把其中不需要本人确认的能力暴露成工具。现在 SDK 版本为 1.2，共 34 项能力（其中 6 项需要用户本人确认，只有用户登录令牌能调用），MCP 把其余 28 项暴露成工具；步骤 06 当时共 32 项能力、26 个工具，步骤 08 新增了只读的“读取档案详情”，步骤 10 新增了只读的“附近餐厅”（服务端没有配置高德密钥时调用会返回 restaurant_not_configured）。医嘱的确认、修改、解除、作废、继续生效、撤回解除建议这 6 个动作不是 MCP 工具，模型只能提出解除建议。授权令牌只代表“你允许这个客户端读取或写入”，吊销后下一次调用立即失效。

先确认开发库已建到最新版本（包含 `agent_grants` 与 `sdk_call_audits` 两张表），都在 `backend` 目录下执行：

```powershell
uv run alembic upgrade head
```

### 如何创建授权

1. 启动后端服务（第 7 节），在 http://localhost:8000/docs 注册、登录、确认免责声明，并 Authorize（第 8 节）。想演示经期，用 `PATCH /api/profile` 把 `gender` 设为 `female`；想看到饮食需求估算，把出生年份、身高、体重、活动水平填全。
2. `POST /api/agent-grants`：`name` 写客户端名（例如 `MCP Inspector`），`access` 选 `read`（只读）或 `read_write`（读写，走完下面的场景需要它），`expires_in_days` 默认 90（1 到 365）。
3. 响应里以 `gl_` 开头的 `token` 就是授权令牌，**只显示这一次**，请立即保存；遗失了只能吊销后重新创建。数据库里只存它的哈希。
4. 同一个分组里还有：`GET /api/agent-grants` 看授权与最近使用时间，`DELETE /api/agent-grants/{grant_id}` 吊销（立即生效），`GET /api/agent-grants/audit` 看自己的调用审计（`limit` 1 到 200，默认 50）。授权令牌不能调用这些接口。

### 如何启动 MCP 服务

MCP 服务由客户端按配置在本机启动（通过标准输入输出通信，不监听端口），手工启动只用来排查问题，在 `backend` 目录下执行：

```powershell
$env:GOODLIFE_AGENT_TOKEN = "gl_你的令牌"
uv run python -m app.mcp_server
```

它会安静地等待客户端的消息，看不到输出是正常的，按 Ctrl+C 退出。可选的 `GOODLIFE_CLIENT_NAME` 是写进审计的客户端名（默认 `mcp`）。数据库地址与密钥读取 `backend/.env`（或客户端配置里设置的同名环境变量），数据库必须在运行；后端服务不需要在运行。令牌只在服务启动时读取，但每次调用都重新核对，所以吊销立即生效、更换令牌要重新连接；不设令牌服务也能启动，只是每次调用都返回未认证。

### 如何用 MCP Inspector 试用

需要 Node.js。在任意目录执行：

```powershell
npx @modelcontextprotocol/inspector
```

在打开的页面里：传输方式选 STDIO；Command 填 uv 的完整路径（`Get-Command uv` 可以查到）；Arguments 填 `--directory 后端目录的完整路径 run python -m app.mcp_server`；Environment Variables 添加 `GOODLIFE_AGENT_TOKEN`（值为令牌），可选 `GOODLIFE_CLIENT_NAME`。点 Connect，在 Tools 页签点 List Tools，应看到 28 个工具，选中一个填参数后 Run Tool。Inspector 的界面会随版本变化，以其官方说明为准。Claude Desktop 的配置同理，详见《接入使用说明》。

### 六个场景

1. 记录经期：`cycle_record_period`（开始日期必填，结束日期可不填）。
2. 查询预测：`cycle_get_prediction`；记录太少时结果照常返回，同时附“数据不足”的提示。
3. 录入医嘱待确认：`medical_submit_order`，原文例如“一周内忌食辛辣，禁酒。”；返回的条目是待确认，`medical_get_constraints` 里没有它。到接口文档页面用登录令牌调 `POST /api/medical/items/{item_id}/confirm` 确认后才生效；之后可以用 `medical_propose_resolution` 提出解除建议，条目仍然生效。工具列表里找不到任何确认或解除医嘱的工具。
4. 记录一餐：`nutrition_search_foods` 搜 `米饭` 取食物编号，再 `nutrition_log_meal`（午餐 `lunch`、克数 150）。
5. 评估食物：`nutrition_evaluate_food`；确认了忌辛辣的医嘱后评估麻婆豆腐，应得到“不建议”并指出是哪条医嘱。
6. 记录训练：`fitness_search_exercises` 搜 `卧推` 取动作编号，再 `fitness_log_workout`（三组：60 千克 10 次、60 千克 8 次、65 千克 6 次），然后 `fitness_get_week_summary`，总训练量 1470。

再创建一个只读授权连接，调用任何写入类工具都得到 `write_not_granted`；不设令牌连接得到 `missing_credential`。最后回到接口文档页面看 `GET /api/agent-grants/audit`，每次调用（含被拒绝的）都有一行，里面没有医嘱原文、备注或令牌。

完整的能力清单、工具清单、授权设计、接入步骤、审计说明与验收记录见 `docs/06-交付物/`。

## 15. 第一阶段整体演示

不经过任何界面，用通用 MCP 客户端把“经期 + 医嘱 + 饮食 + 健身”完整走一遍。数据库在运行、已建表的前提下，在 `backend` 目录执行：

```powershell
uv run python -m app.phase1_demo
```

脚本会重建演示账号 `demo_phase1`（密码 `demo-pass-123`）并签发一个读写授权，然后以子进程方式启动 MCP 服务，通过标准输入输出依次：记录四次经期并查询预测与阶段、录入一条医嘱（只生成待确认条目）、尝试用工具确认（被拒绝）、由“用户本人”确认、评估麻婆豆腐与西瓜等食物、记录早餐与午餐、记录一次轻度和一次高强度训练（后者提示与医嘱冲突）、查看训练后当日能量需求的变化、最后提出解除建议。每一步打印观察到的结果，结尾是审计统计。验收结果见 `docs/第一阶段整体验收记录.md`。

## 16. 多模型接入

步骤 07 让你填写模型服务的地址和密钥，由后端去拉取模型列表、测试连通性，并为不同用途选择不同模型。浏览器不直接带着密钥请求第三方，密钥加密保存在数据库里，接口只回传形如 `****abcd` 的掩码。支持三种服务类型：`openai_compatible`（通义千问、DeepSeek、豆包、智谱、OpenAI 等兼容格式的服务）、`anthropic`（Claude）、`gemini`（Gemini）。

先确认开发库已建到最新版本（包含 `llm_providers`、`llm_models`、`llm_assignments` 三张表），在 `backend` 目录执行：

```powershell
uv run alembic upgrade head
```

### 通过接口文档页面添加并使用一个服务

启动后端服务（第 7 节），在 http://localhost:8000/docs 注册、登录、确认免责声明并 Authorize（第 8 节），然后在 llm 分组里：

1. 看预设：`GET /api/llm/presets` 返回七个预设的服务类型与默认地址，只用来帮你填地址，之后都可以改。
2. 添加服务：`POST /api/llm/providers`，填 `name`（自己起的名字）、`kind`（服务类型）、`base_url`（地址，非本机必须是 https，不能带用户名密码或查询参数）、`api_key`（你自己的密钥）。响应里只有 `key_hint`，没有密钥。
3. 先测一测（可选）：保存前用 `POST /api/llm/providers/test`，保存后用 `POST /api/llm/providers/{provider_id}/test`，再填一个模型编号，结论会区分密钥错误（`invalid_key`）、地址错误（`bad_url`）、模型不可用（`model_unavailable`）等，每种都带中文说明和下一步建议。
4. 获取模型：`POST /api/llm/providers/{provider_id}/fetch-models`，返回模型列表，每个模型带看图、工具调用、对话三项能力的标注（支持、不支持或未知）。有的服务（例如豆包）可能没有模型列表接口，这时用 `POST /api/llm/providers/{provider_id}/models` 手动添加模型编号。
5. 修正能力标注：能力来自随代码维护的对照表，不一定准确；不对的，用 `PATCH /api/llm/models/{model_pk}` 把 `vision`、`tools`、`chat` 改成 true 或 false（null 表示回到对照表）。
6. 分配用途：`PUT /api/llm/assignments/chat`（日常对话）与 `PUT /api/llm/assignments/vision`（看图识别），`model_id` 填模型对象里的 `id`。看图识别只接受明确支持看图的模型，否则返回明确提示。
7. 统一调用：`POST /api/llm/chat`，`purpose` 选 `chat` 或 `vision`，`messages` 里放消息（用户消息可带最多 4 张图片，base64 编码）。后端按用途找到你分配的模型去调用，失败时给出可读的原因（密钥错误、额度不足、模型不存在、超时等）。

完整的接口、字段、错误码、各类型的调用方式与数据说明见 `docs/07-交付物/`。

### 运行实测脚本

步骤 07 的验收要求至少四家服务实测通过，这需要你自己的密钥，所以由你本人在本机运行实测脚本（自动化测试只用假服务，不会访问任何真实服务）。

重要：密钥文件里是你的真实密钥，绝对不能提交到仓库，也不能发给任何人或贴到聊天里。`backend/llm_keys.local.env` 与结果文件 `backend/llm_live_result.md` 已在 `backend/.gitignore` 中忽略；仓库里只保留不含密钥的模板 `backend/llm_keys.local.env.example`。

在 `backend` 目录执行：

```powershell
Copy-Item llm_keys.local.env.example llm_keys.local.env
```

用文本编辑器打开 `llm_keys.local.env`，把你有的服务的密钥填在等号后面（模板里密钥一律留空），按注释填写模型名（豆包要填方舟控制台里的模型名或接入点编号；没有密钥的服务留空，会被跳过），保存为 UTF-8 编码。然后运行：

```powershell
uv run python -m app.llm.live_check
```

脚本对每家服务依次检查拉取模型、对话、工具调用、看图（一张脚本自己生成的纯红色小图），以及三个故意的错误（密钥改错、地址改错、模型名改错，看系统是否归到预期的错误类别），每次调用最多等 60 秒。运行中逐项打印进度，结束后把结果表打印在屏幕上，并写入 `backend/llm_live_result.md`；中途按 Ctrl+C 中断时，已完成的检查也会写进这个文件。输出前会去掉全部密钥，仍请你先看一遍。再把结果摘抄进 `docs/07-交付物/实测记录.md`，并对照 `docs/07-交付物/验收记录.md` 逐条核对。Claude 与 Gemini 目前只做了模拟测试，没有实测。


## 17. 智能体

步骤 08 做出站内智能体：用户在聊天里问“晚饭吃什么”，它按个人档案（医嘱、经期、训练、当日摄入、偏好）动态装配系统指令与工具，调用前面各模块的能力查数据，再用步骤 07 里“日常对话”用途选定的模型回答。规则与引擎定结论，模型只管理解与措辞：

- 输出检查：回答发出前，用引擎逐个核对提到的食物，被医嘱阻断的食物在模型回答里一个字都不许出现，违反就让模型重写一次，仍不行换成固定的安全回答；程序会附上医嘱提醒。依据（来源与说明）只来自引擎，放在 `evidence` 字段里。
- 安全：用药、严重症状、孕期异常、极端节食、自伤的话题，用关键词规则直接给固定的安全回复，不调用模型；系统指令里另有一节安全边界作为第二道防线。
- 医嘱保护：智能体用服务端凭证，能力表里没有医嘱的确认、修改、解除、作废等需本人确认的动作；用户说“医生说我好了”，它只能提出解除建议，由用户在医嘱模块确认。
- 主动开场：用户打开应用时，由规则按优先级挑出今天最该问的一个问题（医嘱复核、经期快到了、昨天训练没记饮食、今天没记饮食、档案久未更新），同一天同类只问一次，拒绝后不再问，可整体关闭，模型只负责措辞。
- 偏好记忆：口味与习惯存在自建的加密偏好表里，写入前过滤医嘱、用药、过敏、病情类内容；用户可以查看与删除。

先确认开发库已建到最新版本（包含 5 张智能体表），在 `backend` 目录执行：

```powershell
uv run alembic upgrade head
```

### 通过接口文档页面试用

启动后端服务（第 7 节），在 http://localhost:8000/docs 注册、登录、确认免责声明并 Authorize（第 8 节），按第 16 节添加模型服务与模型，并把它分配给“日常对话”（智能体要调用工具，请选支持工具调用的模型）。然后在 agent 分组里：

1. 新建会话：`POST /api/agent/conversations`，记下返回的 `id`。
2. 发消息：`POST /api/agent/conversations/{conversation_id}/messages`，`text` 填“晚饭吃什么”，`stream` 设为 `false`（接口文档页面里直接看完整结果；设为 `true` 时是 text/event-stream，先推送若干 `delta`，最后是 `done` 或 `error`）。响应里 `text` 是回答，`evidence` 是依据，`flags` 与 `tools_used` 说明这一轮发生了什么。没有选对话模型时返回 409 `agent_model_not_configured`。
3. 偏好：对话里说“我不吃香菜，记住”，再 `GET /api/agent/preferences` 查看；`DELETE /api/agent/preferences/{preference_id}` 删除。
4. 主动开场：`GET /api/agent/opening` 取今天的开场问题；`POST /api/agent/opening/{opening_id}/decline` 拒绝，`.../answer` 表示已处理；`PUT /api/agent/settings` 可以整体关闭开场。

完整的接口、字段、错误码、规则与验收方法见 `docs/08-交付物/`。

### 运行智能体实测脚本

自动化测试里的模型都是假的，所以验收标准里依赖真实模型表现的第 1、2、9 条，需要你本人用真实模型运行实测脚本。密钥文件与步骤 07 是同一份 `backend/llm_keys.local.env`（做法见第 16 节），至少有一家服务同时填了密钥与模型名；智能体要调用工具，所以脚本优先用 `*_TOOLS_MODEL`，没填就用 `*_CHAT_MODEL`。按服务的顺序，第一家可用的是主要模型，填了第二家的话，脚本会再用它把忌口诱导跑一遍，用来验证换模型后行为仍正常。

重要：密钥文件里是你的真实密钥，不能提交，也不能发给任何人。结果文件 `backend/agent_live_result.md` 已在 `backend/.gitignore` 中忽略，输出前会去掉全部密钥，但里面有脚本建立的临时演示用户的对话，也请先看一遍再决定是否分享。

在 `backend` 目录执行（数据库在运行、已执行 `uv run alembic upgrade head`）：

```powershell
uv run python -m app.agent.live_check
```

脚本会在开发库里建立 5 个临时演示用户（健康、经期、忌辛辣医嘱、健身、医嘱待复核，用户名形如 `live_1a2b3c4d_healthy`，即 live_ 加 8 位十六进制随机编号再加下划线，后面是用户类别），依次运行：每人问“晚饭吃什么”；忌口用户再做三次诱导；健身用户问“训练后吃什么”；待复核用户取开场问题、拒绝后再取一次、再说“医生说我好了”；健康用户问三个风险问题；有第二家模型时，再用它跑一遍忌口诱导。每个场景记录回答全文、`flags`、调用的工具、依据段、是否命中输出检查与耗时，并把结果写入 `backend/agent_live_result.md`。不论成功、失败还是中途按 Ctrl+C，结束时都会删除这 5 个临时用户；如果进程被强行结束，临时用户会留在开发库里，请手动删除用户名符合这个形式（live_ 加 8 位十六进制随机编号再加下划线开头）的用户；只以 `live_` 开头、但不符合这个形式的用户不是脚本建立的，不要删。每次模型调用最多等 60 秒，整个脚本可能要几分钟。

把结果对照 `docs/08-交付物/端到端场景脚本.md` 与 `docs/08-交付物/验收记录.md` 逐条核对。

## 18. 第二阶段中期检查

只用接口、不用界面，把“聊天 + 工具 + 主动开场”完整走一遍。数据库在运行、已建表的前提下，在 `backend` 目录执行：

```powershell
uv run python -m app.phase2_demo
```

脚本会重建检查账号 `demo_phase2`（密码 `demo-pass-123`），并在本机启动一个按关键词应答的模拟模型（不连外网、不用真实密钥），然后通过真实接口依次：配置模型、录入并确认医嘱、取开场问题（再取一次相同、拒绝后不再问）、让智能体用工具记下早餐、问晚饭吃什么（带依据与免责）、诱导推荐忌口食物（被拦截改写并附医嘱提醒）、问停药（固定就医引导、不调模型）、说“医生说我好了”（只提出解除建议，用户本人确认后才解除）、解除后再问、流式输出。结果见 `docs/第二阶段中期检查记录.md`。

## 19. 拍照识别

步骤 09 让你上传一张饭菜照片，由步骤 07 里“看图识别”用途选定的模型认出菜品、份量说法、估计克数与把握程度，再匹配步骤 04 的营养库按克数算出热量与营养。分工是：模型只负责“看”，营养库负责“算”，引擎负责“评”：

- 图片：只收 JPEG、PNG、WebP，不超过 8 MB；后端先转正方向、去掉全部元数据（包括拍摄位置）、长边缩到 1280 像素，再重新编码为 JPEG，发给模型的只是这份 JPEG。原图从不保存；上传时选择保留的，只保存处理后的 JPEG，加密存储，可随记录删除。
- 识别：模型只输出一段 JSON，格式不对时用同一张图片重试一次；不是食物或看不清时直接给出重拍提示，不保存记录。模型给的热量或营养数字一律不读。
- 匹配与计算：菜名在营养库里精确命中（名称、常用名或别名）才算已匹配，否则标为“待确认”，不给数字，附候选让你选；份量按“该食物自带的份量、通用换算表、模型估计的克数、类别默认份量”的顺序换算成克，换算表在 `backend/app/photos/data/portion_units.json`，可以直接修改。每个菜品都带营养库的数据出处。
- 提醒修正：把握程度低于 0.6、待确认、克数小于 10 克或大于 1500 克、克数只来自估算，任一条成立就建议修正。
- 修正与确认：可以改菜名、改份量或克数、从候选里选食物、增删菜品，修改后重新计算；只有确认之后才写入饮食记录（每个菜品一条，备注“拍照识别”），还有待确认的菜品时不能确认。草稿会带上引擎按你今天的约束（医嘱、经期、目标、当日摄入）给出的评价与依据。

先确认开发库已建到最新版本（包含 `photo_recognitions` 表），在 `backend` 目录执行：

```powershell
uv run alembic upgrade head
```

### 通过接口文档页面试用

启动后端服务（第 7 节），在 http://localhost:8000/docs 注册、登录、确认免责声明并 Authorize（第 8 节），按第 16 节添加一个能看图的模型（例如通义千问的 `qwen-vl-max`），并用 `PUT /api/llm/assignments/vision` 把它分配给“看图识别”。然后在 photos 分组里：

1. 上传识别：`POST /api/photos/recognitions`，`file` 选一张饭菜照片，`keep_image` 不填或填 `false`（不保留图片）。响应 201 是一条草稿：`items` 里每个菜品有克数、克数来源、把握程度、`status`（`matched` 或 `needs_confirmation`）、营养、数据出处与 `review_reasons`；`totals` 是已匹配菜品的合计；`evaluation` 是引擎的评价。没有选看图模型时返回 409 `llm_not_configured`，选的模型不能看图时返回 422 `llm_model_lacks_vision`；不是食物或看不清时返回 422 `photo_not_food` 或 `photo_unclear`。
2. 修正：`PUT /api/photos/recognitions/{rec_id}/items`，`items` 放修正后的整组菜品（带 `id` 是修改，不带是新增，没列出的即删除），每项可以改 `name`、`portion_text`、`grams`，或用 `food_id` 从候选里选食物。
3. 确认入库：`POST /api/photos/recognitions/{rec_id}/confirm`，填 `eaten_on`（不能晚于今天）与 `meal_type`。之后用 `GET /api/nutrition/meals` 能看到写入的饮食记录。不想要这次识别时用 `POST /api/photos/recognitions/{rec_id}/discard` 放弃。
4. 识别历史：`GET /api/photos/recognitions`；查看一条：`GET /api/photos/recognitions/{rec_id}`；删除：`DELETE /api/photos/recognitions/{rec_id}`；上传时选择了保留图片的，用 `GET /api/photos/recognitions/{rec_id}/image` 取回处理后的图片。

完整的流程、换算表、数据结构、接口、错误码与验收方法见 `docs/09-交付物/`。

### 照片评测

验收第 8 条要求用至少二十张自选照片评测识别效果，并据此确定哪些情况需要提醒修正。这需要真实的看图模型与你自己拍的照片，所以由你本人在本机运行照片评测脚本（自动化测试只用假服务与程序生成的图片）。

1. 密钥：与第 16 节是同一份 `backend/llm_keys.local.env`，至少有一家服务同时填了密钥与看图模型名（`*_VISION_MODEL`，例如 `QWEN_VISION_MODEL=qwen-vl-max`）；脚本按服务的顺序用第一家填了看图模型名的服务。
2. 照片：在 `backend` 目录下新建 `photo_eval` 目录，放入至少二十张照片（JPEG、PNG 或 WebP），其中放几张不是食物的。
3. 标注：把 `backend/photo_eval.labels.example.csv` 复制到 `backend/photo_eval/labels.csv`，每张照片写一行：文件名、真实菜品（多个用顿号分隔）、真实克数（可不填，填写时与菜品一一对应、用顿号分隔）、是否食物（是或否）。用表格软件编辑时另存为“CSV UTF-8”格式。在 `backend` 目录执行：

```powershell
New-Item -ItemType Directory -Force photo_eval
Copy-Item photo_eval.labels.example.csv photo_eval\labels.csv
```

重要：照片目录 `backend/photo_eval/` 与结果文件 `backend/photo_eval_result.md` 都已在 `backend/.gitignore` 中忽略，不要提交；密钥文件同样不能提交，也不能发给任何人。

然后在 `backend` 目录运行：

```powershell
uv run python -m app.photos.eval_check
```

每张照片走与正式流程相同的步骤（同样的图片处理、提示词、格式重试、解析、营养库匹配与份量换算），不连数据库、不保存任何记录；每次调用最多等 60 秒，运行中逐张打印进度。结束后把结果打印在屏幕上，并写入 `backend/photo_eval_result.md`：每张照片的真实菜品与识别结果（只有菜名与克数，没有图片）、菜品级召回率与精确率、非食物照片的判断情况、各类错误的数量（漏识、多识、认错、匹配不上、克数偏差超过 50%、把握程度低但其实正确、把握程度高但其实错误）、按把握程度分段的正确率与建议的提醒阈值。中途按 Ctrl+C 中断时，已完成的照片也会写进去。输出前会去掉全部密钥，仍请你先看一遍。再把结果摘抄进 `docs/09-交付物/评测记录.md`，并对照 `docs/09-交付物/验收记录.md` 逐条核对。

## 20. 附近餐厅推荐

步骤 10 解决“不想做饭，附近吃点什么”：按你授权的定位或手动输入的地点，用高德开放平台的周边搜索找附近的餐饮场所，再用步骤 04 的引擎按你今天的约束（医嘱、经期、目标、当日摄入）判断每类餐厅适不适合。分工是：高德负责“找店”，规则负责“判断类型、过滤与排序”，引擎负责“评”，模型最多只负责把一句话需求归到固定的需求词上：

- 地点：三选一。坐标（要求先授权定位）、手动输入的地名或地标（可加城市，不需要授权）、已保存的大致区域。拒绝授权后系统不会再次索要，手动地点照常可用；聊天智能体的工具没有坐标参数，需要地点时只会问你在哪里。
- 需求：一句话需求先按固定的 12 个需求词做规则匹配（例如“胃不舒服想喝点粥”归到清淡与粥），没有命中时才请“日常对话”的模型从词表里挑；需求词决定发给高德的检索关键词与排序时偏向的餐厅类型。
- 过滤与排序：18 类餐厅，每类有几道营养库里的代表菜，由引擎逐道评价得出整类结论。例如有已确认的忌辛辣医嘱时，川菜、湘菜、麻辣烫与串串整类避开并说明原因；火锅只有“火锅”这道菜不建议，整类是需要注意。推荐列表按结论、需求偏向的类型、距离、评分排序，最多 20 家。
- 一般性建议：每类给出“可点、适量、应避开”，并固定提示这是基于餐厅类别的一般性建议，不代表该店真实菜单；每家店带一个高德地图的导航链接。
- 隐私：精确坐标、地点文字、需求与检索结果都不入库，没有检索历史；只有勾选“记住大致区域”时，才加密保存区县名称与取整到小数点后两位的坐标，可以随时清除。每个用户每小时最多检索 30 次（计数在后端进程内，只在单进程部署下有效）。

先确认开发库已建到最新版本（包含 `restaurant_settings` 表），在 `backend` 目录执行：

```powershell
uv run alembic upgrade head
```

### 配置高德密钥

1. 在高德开放平台注册开发者账号，创建应用并添加一个“Web 服务”类型的密钥（不是 Web 端、Android 或 iOS 类型）。
2. 把密钥填到 `backend/.env` 的 `AMAP_KEY`；`AMAP_BASE_URL` 与 `AMAP_TIMEOUT_SECONDS`（每次请求每个阶段的超时秒数，默认 8）保持示例值即可。改完重启后端服务。

重要：密钥只放在 `backend/.env` 里，不能提交，也不能发给任何人；它不会出现在日志、错误、响应与审计里。`AMAP_KEY` 留空时附近餐厅功能关闭：检索推荐返回 503 `restaurant_not_configured`，聊天智能体也不提供这个工具；设置与需求词表照常可用。

### 通过接口文档页面试用

启动后端服务（第 7 节），在 http://localhost:8000/docs 注册、登录、确认免责声明并 Authorize（第 8 节）。然后在 restaurants 分组里：

1. 查看设置：`GET /api/restaurants/settings`，新用户 `should_ask_location` 为 `true`（只有从未询问过时为真）。
2. 授权或拒绝：`PUT /api/restaurants/settings/consent`，`consent` 填 `granted` 或 `denied`。
3. 需求词表：`GET /api/restaurants/needs`。
4. 检索推荐：`POST /api/restaurants/search`。手动地点填 `place`（例如 `国贸`）与 `city`（例如 `北京`）；授权后也可以只填 `location`（`lng`、`lat`、`coord_type` 填 `gps`）。可选 `need`（一句话需求）、`needs`（需求词键，最多 3 个）、`radius`（500 到 5000 米，默认 2000）、`remember_area`（是否记住大致区域）。响应里 `restaurants` 是推荐列表（每家有距离、类型、结论与导航链接 `nav_url`），`type_advice` 是每类的到店建议，`avoided_types` 是被避开的类型与原因，`notice` 是一般性建议的固定提示。
5. 清除粗略区域：`DELETE /api/restaurants/settings/area`。

在聊天里（第 17 节）说“不想做饭，我在国贸，附近吃点什么”，智能体会调用附近餐厅工具（服务端配置了高德密钥时才有这个工具）。

完整的位置与数据处理、需求映射、过滤与排序规则、接口、错误码与验收方法见 `docs/10-交付物/`。

### 运行附近餐厅实测脚本

自动化测试里的高德都是假的，所以验收标准第 1、2 条里“真实的高德能不能检索到附近的店”这一部分，需要你本人用真实的高德密钥运行实测脚本。脚本读取的就是上面 `backend/.env` 里的高德配置，没有配置 `AMAP_KEY` 时会说明怎么配置然后退出。

在 `backend` 目录执行（数据库在运行、已执行 `uv run alembic upgrade head`）：

```powershell
uv run python -m app.restaurants.live_check
```

脚本会在开发库里建立 3 个临时用户（普通、忌辛辣医嘱已确认、减脂目标，用户名形如 `live_1a2b3c4d_ordinary`，即 live_ 加 8 位十六进制随机编号再加下划线，后面是用户类别），用正式的检索流程依次检索：北京国贸、上海人民广场、成都春熙路三个手动地点，每个地点三类用户各一次；再用北京天安门广场的大致 GPS 坐标检索一次并记住大致区域；再带一句话需求“想吃点清淡少油的”检索一次，共 11 个场景，一共约 24 次高德请求。每个场景记录检索中心、需求、前 10 家（名称、类型、距离、结论、评分，以及高德原始的类别编码与类别名称）、被避开的类型与原因、各类型的到店建议与耗时，并写入 `backend/restaurant_live_result.md`。不论成功、失败还是中途按 Ctrl+C，结束时都会删除这 3 个临时用户；如果进程被强行结束，临时用户会留在开发库里，请手动删除用户名符合这个形式的用户。

重要：结果文件 `backend/restaurant_live_result.md` 已在 `backend/.gitignore` 中忽略，输出前会去掉密钥，但里面有真实的店名与地址，也请先看一遍再决定是否分享。

把结果摘抄进 `docs/10-交付物/验证场景记录.md`，核对类型表里凭记忆写的高德类别编码，再对照 `docs/10-交付物/验收记录.md` 逐条核对。

## 21. 第二阶段整体验收

只用接口、不用界面，把第二阶段的“聊天、拍照识别、主动开场、餐厅推荐”完整走一遍。数据库在运行、已建表的前提下，在 `backend` 目录执行：

```powershell
uv run python -m app.phase2_acceptance
```

脚本会重建验收账号 `demo_phase2_final`（密码 `demo-pass-123`），并在本机启动两个模拟服务：一个按关键词应答、也会按图片颜色给出固定识别结果的模拟模型，一个返回固定七家店的模拟高德（都不连外网、不用真实密钥；不修改 `backend/.env`，高德地址与密钥由脚本进程的环境变量覆盖，指向模拟服务）。然后通过真实接口依次：中期检查的聊天、工具、主动开场、输出检查、安全边界与流式各步；同一个模型服务下添加看图模型 `qwen-vl-max`，上传照片识别（热量只取自营养库、按医嘱评价）、修正后确认入库、白图报“不是食物”；附近餐厅的拒绝定位、手动地点（忌口避开川菜与麻辣烫、火锅需注意）、授权后记住并清除大致区域；让智能体按地点调用附近餐厅工具并推荐粥铺，核对拍照入库的午餐进入当日汇总与系统指令；最后解除医嘱并复查；结尾核对审计与隐私。共 23 步，结果见 `docs/第二阶段整体验收记录.md`。
