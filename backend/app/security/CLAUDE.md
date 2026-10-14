# security 包说明书

## 职责
- 三件密码学工具，别的包只调用、不自己实现：
  - passwords.py：argon2 密码哈希与校验；
  - tokens.py：登录令牌（HS256，带用户编号与 token_version，过期时间取配置）；
  - crypto.py：字段加密（Fernet，密钥来自配置的 FIELD_ENCRYPTION_KEY），EncryptedJSON 存任意 JSON 值、EncryptedBytes 存文件字节。
- 健康相关的明文字段（档案身高体重与健康状况、医嘱原文与条目、经期日志、饮食与训练备注、对话内容、模型密钥、照片与证据文件等）都靠这里的两种列类型落库为密文。

## 边界
- 依赖：只引用 config。处于最底层，被 auth、各业务包的 models、sdk 引用。
- 不认识用户、数据库会话或业务概念；不做权限判断（那是 auth、disclaimer 与各模块 deps 的事）。
- 字段加密密钥与 JWT 密钥由配置在启动时校验，配置不合法时 create_app 启动即失败；本包不提供默认密钥。

## 入口
- passwords.hash_password、verify_password；tokens.create_access_token、decode_access_token、InvalidTokenError；crypto.EncryptedJSON、EncryptedBytes、encrypt_value、decrypt_value。
- 测试：tests/test_security.py、tests/test_config.py；迁移里的加密转换见 tests/test_migrations.py。

## 禁区
- 不记录、不返回、不在异常说明里带出明文、密文、密钥或令牌。
- 不换加密算法或密文格式而不写迁移：库里已有的密文要能继续解开（迁移 0006 就是把明文状态转成密文的先例）。
- 不在别的包里直接用 Fernet、jwt 或 argon2；需要新的密码学能力就加在这里并写测试。
- 测试只用 conftest 里固定的测试密钥，不读 backend/.env。
