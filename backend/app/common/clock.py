from datetime import date


def get_today() -> date:
    """当前日期。单独做成依赖，测试里可以替换成固定日期。"""
    return date.today()
