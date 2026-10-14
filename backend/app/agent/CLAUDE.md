# agent 包说明书

## 职责
- 站内智能体：对话（流式与非流式）、按档案装配工具与系统指令、偏好记忆、主动开场、风险话题与输出检查。
- 一轮对话（loop.py 的 run_turn）：保存用户消息 → 风险话题（safety.py，命中直接给固定安全回复，不调模型、不调工具）→ 装配（assembly.py）→ 调模型与执行工具（最多 MAX_MODEL_CALLS 次）→ 输出检查（guard.py）→ 附医嘱提醒与健康提示 → 保存。
- 依据只来自营养引擎（经 SDK 的 nutrition.evaluate_food），原样放在 evidence 里；模型自写的“依据”段会被去掉。
- 风险话题按 自伤、严重症状、孕期异常、用药、极端节食 的优先级判断，未成年用户多一类未成年减重；每类固定回复都含 120 急救或就医指引。
- clues.py 识别“医生说我好了”这类说法，只让系统指令多一句：智能体只能提出解除建议。

## 边界
- 依赖：sdk（AgentCredential 加客户端名 agent，因此每次读写都有审计）、llm（调模型）、各业务模块的少量常量与读取、restaurants.amap 的 amap_configured。
- 不被任何业务包引用；main 挂载 router；frontend/src/lib/contract.ts 抄了这里的固定文案（tests/test_frontend_contract.py 逐字核对）。
- 工具只来自 sdk.tooling.agent_registry（已去掉 user_confirmed 能力）加 remember_preference；工具调用只认本轮发给模型的声明。
- 用户自己写的文字（档案偏好与忌口、医嘱内容、偏好记忆）放进【用户资料】资料块，压平换行并替换【】，不能冒充指令或另起一节。
- 经期未开放（或未单独同意，步骤 12 任务 3a 起）时，工具与系统指令里都不出现“经期”。

## 入口
- 路由：/api/agent 下的 conversations、conversations/{id}/messages、preferences、settings、opening 与 opening/{id}/decline、answer（router.py），都经 require_disclaimer_user。
- 实测脚本：uv run python -m app.agent.live_check，由用户本人用真实模型运行。
- 测试：tests/test_agent_loop.py、test_agent_rules.py、test_agent_guard.py、test_agent_openings.py、test_agent_store.py、test_agent_live_check.py、test_agent_docs.py、test_minors.py；模拟模型在 tests/agent_fake.py。

## 禁区
- 绝不把医嘱的确认、修改、作废、继续或解除做成工具，也不让模型声称已经替用户确认或解除；最多 propose_resolution。
- 风险话题命中时不调模型；不改固定回复里的 120 与热线，不回放风险话题的原话。
- 偏好记忆只收口味与习惯，拿不准一律拒绝；医嘱与健康状况永远从医嘱与档案模块读取。
- 不跳过输出检查：回答提到医嘱阻断或无法核对的食物时重写一次，仍不通过就用固定的安全回答。
- 对话正文、工具参数与结果不写日志；测试只用 MockTransport 模拟模型，绝不访问真实网络。
