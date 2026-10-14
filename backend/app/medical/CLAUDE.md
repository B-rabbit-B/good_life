# medical 包说明书

## 职责
- 医嘱模块：医嘱原文与证据文件、提取出的条目、条目状态流转（待确认 → 生效中 → 待复核 → 已解除，或作废）、每一步的审计事件、当前生效约束与复核清单。
- 分工：orders.py 管原文、证据（单个文件上限 10 MB，加密存字节）与手动补充条目；extraction.py 是规则提取器，只产出“待确认”的候选条目；items.py 管状态流转、审计与约束查询。
- 生效中与待复核的条目都是硬约束（HARD_CONSTRAINT_STATUSES）：待复核期间、用户确认解除之前仍按原要求执行。

## 边界
- 依赖：auth、common、db、disclaimer、errors、profile、security。不引用 llm：提取至今是规则提取器（get_extractor），接模型提取时也只能产出待确认条目。
- 被引用：fitness（运动限制冲突）、nutrition（忌口是硬约束）、restaurants、sdk 的 medical 能力、agent；common/body_limit.py 只取 MAX_EVIDENCE_BYTES。
- 门槛：deps.require_medical_user（免责 → 模块开放 → 每次请求前刷新到期状态）；sdk 复用它。步骤 12 起这里还要加单独同意的检查（任务 3a）。

## 入口
- 路由：/api/medical 下的 orders、orders/{id}/items、orders/{id}/evidence、evidence/{id}、items 与 items/{id} 的 confirm、void、continue、propose-resolution、cancel-proposal、resolve、events，以及 events、constraints、reviews（router.py）。
- 演示数据：uv run python -m app.medical.demo；样例医嘱在 samples.py（虚构）。
- 测试：tests/test_medical_extraction.py、test_medical_items.py、test_medical_orders.py、test_medical_api.py、test_medical_demo.py、test_medical_docs.py；SDK 侧 test_sdk_capabilities.py。

## 禁区
- USER_ONLY_OPERATIONS（确认、修改、作废、继续执行、解除、撤销解除建议）只能由用户本人经网页接口或用户登录令牌触发，审计来源记为 user；绝不能做成智能体或 MCP 可调用的工具。智能体最多调用 propose_resolution 提出建议，不改变约束。
- 提取器（无论规则还是将来的模型）不得直接生成生效条目；拿不准时宁可低把握并提示核对，也不给“看起来很确定”的错误约束。
- 每一次创建、修改与状态变化都要写审计事件；不要绕过 items.py 直接改 status。
- 原文、条目内容、涉及对象、解除理由、证据文件名与字节都必须保持加密列；日志不记任何医嘱内容。
