# llm 包说明书

## 职责
- 多模型接入：用户自己配置模型服务（地址、密钥），后端拉取模型列表、标注看图与工具调用能力、测试连通、为“日常对话”（chat）与“看图识别”（vision）两种用途各选一个模型，并用统一接口调用。
- adapters/ 把 OpenAI 兼容、Claude、Gemini 三种协议换成中立的消息、工具调用与错误类型（adapters/base.py）；service.py 管配置、能力判断与 complete/resolve_target；urls.py 检查服务地址不是内网。
- 密钥只存密文（EncryptedJSON，且延迟加载，只有真正调用服务的代码才读）；接口与界面只给掩码（key_hint：末 4 位，不足 8 位一位都不露）。

## 边界
- 依赖：auth、common、config、db、disclaimer、errors、security。不认识任何业务模块。
- 被引用：photos（看图）、restaurants（需求挑词，可选）、agent（对话与工具调用）。业务包只经 service 的 resolve_target、complete 与 adapters/base 的中立类型调用模型，不直接拼某家协议。
- 服务地址在保存时与每次出站前都复查（防止保存后解析成内网）；只有测试与本机模拟服务可以用 LLM_ALLOW_PRIVATE_HOSTS 放开。
- 调用模型期间不持有数据库事务：读配置用短会话，调用在会话之外。

## 入口
- 路由：/api/llm 下的 presets、providers（增删改查、test、fetch-models、models）、models/{id}、assignments/{purpose}、chat（router.py），都经 require_disclaimer_user。
- 适配器工厂：service.get_adapter_factory（测试用 MockTransport 替换，绝不访问真实网络）。
- 实测脚本：uv run python -m app.llm.live_check，由用户本人用不提交的 llm_keys.local.env 运行。
- 测试：tests/test_llm_adapters.py、test_llm_config.py、test_llm_service.py、test_llm_tool_roundtrip.py、test_llm_live_check.py、test_llm_docs.py。

## 禁区
- 密钥不进日志、错误说明、响应、repr 与实测结果文件；Gemini 的密钥放请求头，不放进地址。
- 不让模型服务地址指向内网或本机（测试开关除外），不要省掉出站前的复查。
- 不在这里写业务提示词或业务规则：提示词属于 photos、agent、restaurants。
- 新增服务类型要同时补适配器、错误归类与能力表（data/capabilities.json）和对应测试。
