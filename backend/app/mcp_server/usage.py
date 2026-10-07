"""每个 MCP 工具的使用说明：（什么时候用，什么时候不要用）。只覆盖暴露给智能体的能力，绝不包含 user_confirmed 能力。"""

TOOL_USAGE: dict[str, tuple[str, str]] = {
    "profile.get_capabilities": (
        "对话开始时、或调用其他工具返回模块未开放时用，先弄清用户开放了经期、医嘱、饮食、健身中的哪些模块",
        "已经知道模块开放情况时不要反复调用；它不返回用户档案详情，也不能用来开通模块",
    ),
    "cycle.list_periods": (
        "用户想回顾自己记录过的经期，或你要核对某次经期是否已经记过、避免重复记录时用",
        "想看平均周期、规律性等统计时不要用，改用 cycle_get_stats；想知道下次经期时不要用，改用 cycle_get_prediction",
    ),
    "cycle.record_period": (
        "用户明确告诉你经期开始（或开始与结束）的具体日期、要求记下来时用；结束日期未知可以留空",
        "日期含糊（如“前几天”）时不要猜，先问清具体日期；只是询问或闲聊经期时不要用；记录前可用 cycle_list_periods 确认没有重复",
    ),
    "cycle.get_stats": (
        "用户问自己的周期平均多长、规不规律、经期一般几天、常见症状时用",
        "想知道下次经期或排卵日时不要用，改用 cycle_get_prediction；想知道某天处于哪个阶段时不要用，改用 cycle_get_phase",
    ),
    "cycle.get_prediction": (
        "用户问下次经期什么时候来、排卵日或易孕窗口时用；回答时说明预测仅供参考，数据不足时如实告知并建议补记",
        "不要把预测结果当作避孕或备孕的医学依据；只想知道今天处于哪个阶段时改用 cycle_get_phase",
    ),
    "cycle.get_phase": (
        "需要知道某一天（默认今天）处于经期、卵泡期、排卵期还是黄体期，或距下次经期还有几天时用",
        "想要该阶段的饮食与生活建议时不要用，改用 cycle_get_tips；想看长期统计时改用 cycle_get_stats",
    ),
    "cycle.get_tips": (
        "用户想知道某一天（默认今天）所处经期阶段该怎么吃、怎么调养、生活上注意什么时用",
        "评估某种具体食物能不能吃时不要用，改用 nutrition_evaluate_food；不要把小贴士当作医疗建议",
    ),
    "medical.submit_order": (
        "用户提供医生的医嘱、病历或复诊单原文、希望录入时用；只会生成待用户确认的条目，不会立即生效，提交后提醒用户到应用里逐条确认",
        "不要自己编写或改写医嘱内容再提交，只提交用户给出的原文；用户只是询问已有医嘱时不要用，改用 medical_list_items 或 medical_get_constraints",
    ),
    "medical.list_items": (
        "用户想浏览自己的医嘱条目，或你需要按状态、类别查找某条医嘱的编号时用",
        "只想知道今天必须遵守哪些限制时不要用，改用 medical_get_constraints；已经知道编号想看详情时改用 medical_get_item",
    ),
    "medical.get_item": (
        "已经拿到某条医嘱条目的编号、需要查看其完整内容、状态与日期时用",
        "不知道编号时不要猜，先用 medical_list_items 查找；不要用它批量浏览医嘱",
    ),
    "medical.get_constraints": (
        "给出任何饮食、运动建议之前用，读取今天生效的医嘱约束并严格遵守；用户问“我现在有哪些忌口或限制”时也用",
        "想看全部历史条目（包括已解除、已作废、待确认的）时不要用，改用 medical_list_items",
    ),
    "medical.list_reviews": (
        "提醒用户哪些医嘱到期需要复核、哪些有待处理的解除建议时用",
        "不要替用户完成复核或确认，复核结果只能由用户本人在应用里处理；想看今天的约束时改用 medical_get_constraints",
    ),
    "medical.propose_resolution": (
        "用户说医生已允许停止某条医嘱（例如复查后解除限制），需要提出解除建议并写明理由时用；只是建议，用户在应用里确认后才会解除，在此之前约束照常生效",
        "不要仅凭自己的判断或用户的随口一说就提出解除；不能用它代替用户确认，也不能用来修改或作废医嘱，这些只能由用户本人在应用里操作",
    ),
    "nutrition.search_foods": (
        "用户提到某种食物、需要找到它在食物库里的编号时用（记录饮食、评估食物之前通常先调用）；有多个候选时与用户确认是哪一种",
        "已经知道食物编号时不要重复搜索；想看某种食物的营养详情时改用 nutrition_get_food",
    ),
    "nutrition.get_food": (
        "已经拿到食物编号、需要查看每 100 克营养素、标签、常用份量与数据来源时用",
        "不知道编号时不要猜，先用 nutrition_search_foods；想判断用户今天能不能吃时不要用，改用 nutrition_evaluate_food",
    ),
    "nutrition.log_meal": (
        "用户明确说吃了什么、吃了多少（克数或份量）、要求记下来时用；每次记录一项食物，克数与份量只填一项",
        "只是询问能不能吃时不要用，改用 nutrition_evaluate_food；分量不明确时先问清楚，不要自己编造分量",
    ),
    "nutrition.list_meals": (
        "用户想看某一天（默认今天）具体记录了哪些饮食及每项的营养素时用",
        "只想知道全天总摄入和还剩多少额度时不要用，改用 nutrition_get_daily_summary",
    ),
    "nutrition.get_daily_summary": (
        "用户问某一天（默认今天）吃了多少热量、蛋白质等，以及距离每日需求还剩多少时用；档案不完整无法估算需求时如实告知并引导补充",
        "想看逐条饮食明细时不要用，改用 nutrition_list_meals；不要用它判断某种食物能不能吃",
    ),
    "nutrition.evaluate_food": (
        "用户问“这个能不能吃”“吃多少合适”等关于单种食物的问题时用，它会综合医嘱约束、经期阶段、目标、训练与今日摄入给出结论和理由",
        "用户已经吃了、要求记录时不要用，改用 nutrition_log_meal；一餐里有多种食物时改用 nutrition_evaluate_meal",
    ),
    "nutrition.evaluate_meal": (
        "用户想评估一餐中的多种食物（如一份套餐或一桌菜）是否合适时用，会给出逐项与整体结论",
        "只问单种食物时改用 nutrition_evaluate_food；用户已经吃完要求记录时不要用，改用 nutrition_log_meal",
    ),
    "fitness.search_exercises": (
        "用户提到某个训练动作、需要找到它在动作库里的编号时用（记录训练、查看动作趋势之前通常先调用）；有多个候选时与用户确认是哪一个",
        "已经知道动作编号时不要重复搜索；不要用它推荐训练计划",
    ),
    "fitness.log_workout": (
        "用户明确说完成了一次训练、给出了日期、动作及组数次数或时长、要求记下来时用；与运动限制医嘱冲突时会返回提示，要如实转告用户",
        "用户只是计划或询问训练时不要用；重量、次数等关键信息缺失时先问清楚，不要自己编造",
    ),
    "fitness.list_workouts": (
        "用户想回顾一段日期内（默认最近 7 天）的训练记录及其与医嘱的冲突提示时用",
        "只想看某周的汇总数据时不要用，改用 fitness_get_week_summary；只关心今天的训练对饮食的影响时改用 fitness_get_training_signal",
    ),
    "fitness.get_week_summary": (
        "用户想了解某一周（默认本周）练了几次、训练量、各肌群分布、有氧时长与估算消耗时用",
        "想看逐条训练明细时不要用，改用 fitness_list_workouts；开始日期不是星期一时不要硬填，默认本周即可",
    ),
    "fitness.get_exercise_trend": (
        "用户想知道某个力量动作的进步情况（最大重量、训练量的变化）时用；需要先拿到动作编号",
        "不知道动作编号时先用 fitness_search_exercises；不适用于有氧动作或整体训练回顾",
    ),
    "fitness.get_training_signal": (
        "给饮食建议前想知道用户今天是否训练、强度如何、练了哪些肌群、估算消耗多少时用",
        "想回顾过去的训练时不要用，改用 fitness_list_workouts 或 fitness_get_week_summary",
    ),
}
