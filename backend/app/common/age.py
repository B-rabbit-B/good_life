"""年龄判断：按“当年减出生年份”计算（档案只有出生年份，可能比实际大一岁；用户也可能谎报）。"""

from datetime import date

MIN_AGE = 14  # 不满 14 周岁不服务（个人信息保护法第三十一条：选择不服务，而不做监护人同意）
ADULT_AGE = 18


def age_in_years(birth_year: int, today: date) -> int:
    return today.year - birth_year


def is_minor(birth_year: int | None, today: date) -> bool:
    """没有填写出生年份时不算未成年。"""
    return birth_year is not None and age_in_years(birth_year, today) < ADULT_AGE
