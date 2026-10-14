# backend/migrations 目录说明书

## 职责
- Alembic 数据库迁移：versions/ 下按编号排列的手写迁移，从 0001_users 到当前最新的 0016_restaurants。env.py 经 app.models 拿到全部模型、经配置拿数据库地址。
- 迁移是数据库结构的唯一来源：应用启动不建表，测试会话开始时把测试库迁移到最新（tests/conftest.py），端到端服务器同样如此。

## 边界
- 只描述表结构与必要的数据转换（例如 0006 把经期状态从明文转成密文）；业务规则不写在迁移里。
- 迁移与模型必须一致：tests/test_migrations.py 的 test_migrations_match_models 用 compare_metadata 比对，有任何差异都失败。
- 迁移里需要加密或解密时用 app.security.crypto，与模型的加密列同一套密钥与格式。

## 入口
- 应用迁移：在 backend 目录运行 uv run alembic upgrade head；回退一步 uv run alembic downgrade -1。
- 新迁移：文件名与 revision 都写成“四位编号_简短英文名”（例如 0017_sensitive_consents），down_revision 指向当前最新；步骤 12 只新增 0017_sensitive_consents（任务 3a）。
- 测试：tests/test_migrations.py（与模型一致、加密转换迁移的升降级）。

## 禁区
- 不用 autogenerate 直接提交：自动生成的结果只能参考，迁移要手写并逐列核对类型、可空、默认值、索引与外键的级联方式（业务表的 user_id 一律 ON DELETE CASCADE）。
- 每个迁移都要有可用的 downgrade（能真正回到上一版本，含数据转换的反向），不写空的 downgrade。
- 不改已经提交的迁移（别人的库已经跑过）；要改结构就新增一个迁移。
- 不在迁移里写入演示数据或真实数据。
