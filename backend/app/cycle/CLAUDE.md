# cycle 包说明书

## 职责
- 经期模块：经期记录、每日记录（症状等，加密）、经期设置（记录中、已标记孕期、暂停三种状态，加密）、统计、预测、阶段判断与阶段提示。
- 分三层：records.py 读写与校验（开始日不重复、结束不早于开始、两次经期不重叠）→ insights.py 把数据交给引擎并处理暂停状态 → engine.py 纯计算（不碰数据库、不读时间，日期由调用方传入）。
- 阶段提示来自 tips_rules.json，回答里总带 TIPS_DISCLAIMER：预测与提示不能用于避孕或诊断。

## 边界
- 依赖：auth、common、db、disclaimer、errors、profile、security。
- 被引用：nutrition（经期阶段是饮食引擎的软约束）、sdk 的 cycle 能力、agent（工具与系统指令）。
- 门槛：deps.require_cycle_user，建在免责门槛上，再按 compute_capabilities 判断经期是否开放（403 cycle_not_available）；sdk 的模块准入复用同一个函数。步骤 12 起这里还要加单独同意的检查（任务 3a）。
- 暂停状态下预测给 paused、阶段给 unknown，不做推算。

## 入口
- 路由：/api/cycle 下的 periods、settings、day-logs、stats、prediction、phase、tips（router.py），全部经 require_cycle_user。
- 演示数据：uv run python -m app.cycle.demo（demo.py，三位演示用户）。
- 测试：tests/test_cycle_engine.py、test_cycle_records.py、test_cycle_insights.py、test_cycle_tips.py、test_cycle_demo.py、test_cycle_docs.py。

## 禁区
- 引擎保持纯函数：不要在 engine.py 里查库或调用 date.today，校验留在 records.py。
- 经期能力只给开放了经期的用户：不要绕过 require_cycle_user 直接查经期表；智能体对未开放经期的用户连“经期”二字都不能提。
- 不把预测说成医学结论：新增的文案也要保留“仅供参考、不能用于避孕或诊断”的意思。
- 设置状态与每日记录必须保持加密列。
