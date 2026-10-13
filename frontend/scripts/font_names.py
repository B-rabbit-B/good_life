"""给生成的子集改名并写明修改说明（SIL OFL 1.1 第 2、3 条）。

用法：uv run --no-project --with "fonttools[woff]" python scripts/font_names.py <woff2> <家族名> <样式名> <修改说明>
子集是 OFL 所说的修改版：家族名、全名、PostScript 名与唯一标识都换成中性的名字（不能用保留字体名“Source”），
版权（名称 0）原样保留并在后面附上修改说明，许可证说明与网址（名称 13、14）保留。原地改写，仍是 woff2。
"""

import sys

from fontTools.ttLib import TTFont

RENAMED = (1, 2, 3, 4, 6, 16, 17)


def main() -> None:
    path, family, style, note = sys.argv[1:5]
    font = TTFont(path, recalcTimestamp=False)  # 不改时间戳：同样的输入生成逐字节相同的文件
    name = font["name"]
    copyright_record = name.getName(0, 3, 1, 0x409) or name.getName(0, 1, 0, 0)
    copyright_text = copyright_record.toUnicode() if copyright_record is not None else ""
    full = f"{family} {style}"
    values = {
        0: f"{copyright_text} {note}".strip(),
        1: family,
        2: style if style in ("Regular", "Bold") else "Regular",
        3: f"{full}; good-life subset",
        4: full,
        6: f"{family}-{style}".replace(" ", ""),
    }
    if style not in ("Regular", "Bold"):  # 非四种基本样式时，名称 1 带上样式，名称 16、17 给出家族与样式
        values[1] = full
        values[16] = family
        values[17] = style
    for name_id in (0, *RENAMED):
        name.removeNames(nameID=name_id)
    for name_id, value in values.items():
        name.setName(value, name_id, 3, 1, 0x409)
    if "CFF " in font:  # CFF 字体在 CFF 表里还有一份名字
        cff = font["CFF "].cff
        cff.fontNames = [values[6]]
        top = cff.topDictIndex[0]
        top.FullName = full
        top.FamilyName = family
    font.save(path)


if __name__ == "__main__":
    main()
