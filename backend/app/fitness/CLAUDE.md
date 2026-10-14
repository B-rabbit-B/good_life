# fitness 包说明书

## 职责
- 健身模块：内置动作库（data/exercises.json，只读，不入库）与自定义动作、训练记录、周汇总与动作趋势、能量消耗估算、今日训练信号、运动限制类医嘱的冲突提示。
- calc.py 与 conflicts.py 是纯函数；summaries.py、signals.py 从数据库读出训练后交给它们计算；workouts.py 管自定义动作与训练记录。
- 冲突检测只提示、不阻止记录训练；医嘱里的说法按 data/limit_terms.json 对应到训练特征，对不上的给“无法判断，请自行核对”。

## 边界
- 依赖：auth、common、db、disclaimer、medical（读取运动限制）、profile、security。
- 被引用：nutrition（当天训练是饮食引擎的上下文）、sdk 的 fitness 能力、agent（最近有训练时才提供查询类工具）。
- 门槛：deps.require_fitness_user（免责 → 模块开放）；sdk 复用它。
- 训练信号只描述某一天练了什么、强度、估算消耗与冲突，不给任何饮食结论；饮食结论由 nutrition 给。

## 入口
- 路由：/api/fitness 下的 exercises/search、exercises/custom、exercises/{id}、exercises/{id}/trend、exercises、workouts、summary/week、signal（router.py）。
- 演示数据：uv run python -m app.fitness.demo。
- 测试：tests/test_fitness_calc.py、test_fitness_conflicts.py、test_fitness_library.py、test_fitness_signal.py、test_fitness_summaries.py、test_fitness_workouts.py、test_fitness_demo.py、test_fitness_docs.py。

## 禁区
- 不因为冲突拒绝保存训练，也不替用户改训练内容；只给提示与依据。
- 能量消耗是估算区间，不要写成精确数字或医疗指标。
- 别人的自定义动作与不存在的动作一样回 404 exercise_not_found（沿用既有错误码，不改成 not_found）。
- 不在本包里写饮食建议，也不引用 nutrition（方向是 nutrition 引用 fitness）。
