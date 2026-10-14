# agent 包说明书

## 职责
- 站内智能体：对话（流式与非流式）、按档案装配工具与系统指令、偏好记忆、主动开场、风险话题与输出检查。
- 一轮对话（loop.py 的 run_turn）：保存用户消息 → 风险话题（safety.py，命中直接给固定安全回复，不调模型、不调工具）→ 装配（assembly.py）→ 调模型与执行工具（最多 MAX_MODEL_CALLS 次）→ 输出检查（guard.py）→ 附医嘱提醒与健康提示 → 保存。
- 依据只来自营养引擎（经 SDK 的 nutrition.evaluate_food），原样放在 evidence 里；模型自写的“依据”段会被去掉。
- 风险话题按 自伤、严重症状、孕期异常、用药、极端节食 的优先级判断，未成年用户多一类未成年减重；每类固定回复都含 120 急救或就医指引。
- clues.py 识别“医生说我好了”这类说法，只让系统指令多一句：智能体只能提出解除建议。

## 边界
- 依赖：sdk（AgentCredential 加客户端名 agent，因此每次读写都有审计）、llm（调模型）、各业务模块的少量常量与读取、restaurants.amap 的 amap_configured、consents 的 CONSENT_KINDS 与 has_consent（回放时判断单独同意）。
- 不被任何业务包引用；main 挂载 router；frontend/src/lib/contract.ts 抄了这里的固定文案（tests/test_frontend_contract.py 逐字核对）。
- 工具只来自 sdk.tooling.agent_registry（已去掉 user_confirmed 能力）加 remember_preference；工具调用只认本轮发给模型的声明。
- 用户自己写的文字（档案偏好与忌口、医嘱内容、偏好记忆）放进【用户资料】资料块，压平换行并替换【】，不能冒充指令或另起一节。
- 偏好是持久化的注入链：写入时 check_preference 过滤（短语级的指令、身份操控、引流说法与网址，INSTRUCTION_WORDS 与 _DOMAIN），
  assembly._read_preferences 读出时再过滤一次（旧数据同样受新规则约束；列表接口不过滤，用户能看到并删除）。
  开场改写也用 preferences.instruction_like 把关，带指令或网址就用模板。
- 注入的硬边界（tests/test_injection_bounds.py 用“完全听从”的脚本化模型证明）：拿不到 user_confirmed 工具、别人的编号只得到
  not_found、资料块不能被突破、输出检查照样拦截医嘱禁忌食物、6 个写入工具都有审计。改装配、工具或输出检查时这些测试必须仍然通过。
- 经期未开放或用户没有单独同意时，工具与系统指令里都不出现“经期”。装配读经期阶段或医嘱约束遇到 consent_required 时，本轮把该模块当作未开放（不提供工具、不记为读不到）；医嘱未同意时约束一节写 MEDICAL_NOT_CONSENTED，没有饮食医嘱，输出检查不会因此重写。
- 回放历史时（loop.replayable），用户当前没有单独同意的模块（直接查 consents.has_consent），其工具调用连同同组结果都不回放：撤回同意后不再把对话里保存的经期、医嘱工具结果发给模型服务。对话里用户与助手自己写的文字不在此列（同意文案已说明对话副本不随撤回删除）。
- 清空全部对话（conversations.clear_all，DELETE /api/agent/conversations）删除本人全部会话（消息级联）与全部开场记录，偏好与设置不动；撤回同意与删除账号之外，这是用户清掉对话副本的入口。

## 入口
- 路由：/api/agent 下的 conversations（含 DELETE 清空全部）、conversations/{id}/messages、preferences、settings、opening 与 opening/{id}/decline、answer（router.py），共 14 个，都经 require_disclaimer_user。
- 实测脚本：uv run python -m app.agent.live_check 与红队脚本 uv run python -m app.agent.redteam_check（11 个注入攻击，成功率只数硬边界被突破的次数，结果写 redteam_live_result.md），都由用户本人用真实模型运行。
- 测试：tests/test_agent_loop.py、test_agent_rules.py、test_agent_guard.py、test_agent_openings.py、test_agent_store.py、test_agent_live_check.py、test_agent_docs.py、test_minors.py、test_consents.py（未同意的模块当作未开放）、test_injection_bounds.py、test_preference_injection.py、test_redteam_check.py；模拟模型在 tests/agent_fake.py。

## 禁区
- 绝不把医嘱的确认、修改、作废、继续或解除做成工具，也不让模型声称已经替用户确认或解除；最多 propose_resolution。
- 风险话题命中时不调模型；不改固定回复里的 120 与热线，不回放风险话题的原话。
- 偏好记忆只收口味与习惯，拿不准一律拒绝；医嘱与健康状况永远从医嘱与档案模块读取。
- 不跳过输出检查：回答提到医嘱阻断或无法核对的食物时重写一次，仍不通过就用固定的安全回答。
- 对话正文、工具参数与结果不写日志；测试只用 MockTransport 模拟模型，绝不访问真实网络。
- 红队脚本的附近餐厅攻击只用脚本内置的模拟高德（临时换掉 amap 的配置与传输层，用完换回），不访问真实高德、不用真实高德密钥；Claude 不运行红队脚本。
