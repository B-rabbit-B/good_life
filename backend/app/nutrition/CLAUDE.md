# nutrition 包说明书

## 职责
- 营养库与饮食约束引擎，是全项目“这个能不能吃”的唯一依据：拍照识别、附近餐厅、智能体的依据段与输出检查都调用这里的引擎。
- catalog.py 从 data 下的数据文件加载营养库（只读参考数据，不入数据库），每个食物带出处与授权状态（中国食物成分表整理数据固定版本并校验哈希、自建菜品、手动补充）。
- context.py 把已确认医嘱（硬约束）、经期阶段、档案目标与偏好、当天训练、当日摄入组装成上下文；engine.py 是纯函数，同样输入同样输出，依据去重后按固定规则排序。
- meals.py 是饮食记录与每日汇总；needs.py 估算每日需求（未满 18 周岁不估算，只给说明）。

## 边界
- 依赖：auth、common、cycle、db、disclaimer、errors、fitness、medical、profile、security。
- 被引用：photos、restaurants、sdk 的 nutrition 能力、agent（依据与输出检查）。
- 门槛：deps.require_nutrition_user（免责 → 模块开放）；photos 与 restaurants 的路由也用它。
- 医嘱是硬约束，档案忌口与偏好是软约束；软约束不能把医嘱禁止的结论放宽。

## 入口
- 路由：/api/nutrition 下的 foods/search、foods/{id}、tags、meals、summary、needs、evaluate、evaluate-meal（router.py）。
- 演示数据：uv run python -m app.nutrition.demo。数据文件在 data/，标签与词汇表加载时校验引用。
- 测试：tests/test_nutrition_engine.py、test_nutrition_engine_real.py（真实营养库的回归，沿用前者的夹具）、test_nutrition_catalog.py、test_nutrition_data.py、test_nutrition_meals.py、test_nutrition_needs.py、test_nutrition_evaluate.py、test_nutrition_training.py、test_nutrition_raw_cold.py、test_nutrition_demo.py、test_nutrition_docs.py。

## 禁区
- 引擎不读数据库、时间或随机数；需要的东西都由 context.py 准备后传入。
- 热量与营养只由营养库每 100 克数值乘克数得出，不取自任何模型输出。
- 不改成分表原始数据文件（哈希校验会失败）；补充数据走手动补充与自建菜品，并写明出处与授权状态。
- 营养库总数与“仅供个人学习”的数目被交付文档引用，增删食物时同步检查文档与测试。
- 未成年用户不给能量需求数字，上下文里不带减脂、增肌目标（context.py 置空 goal）；不要在别处绕回去。
