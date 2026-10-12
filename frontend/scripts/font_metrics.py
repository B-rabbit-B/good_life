"""读出字体的度量，供 subset-fonts.mjs 生成回退字体的 ascent-override、descent-override 与 size-adjust。

用法：uv run --no-project --with fonttools python scripts/font_metrics.py <字体文件> [--covers <文本文件>]
输出一行 JSON：unitsPerEm、ascender、descender（负数）、lineGap、digitAdvance（0 到 9 的平均字宽，没有数字时为 null），
给了 --covers 时再加 covered（文本文件里的字中字体确实有字形的那些，按码位排序去重）。
ascender 与 descender 按手机浏览器的取法：字体设了 USE_TYPO_METRICS 时取 OS/2 的 typo 值，否则取 hhea。
"""

import argparse
import json
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

USE_TYPO_METRICS = 1 << 7


def metrics(font: TTFont) -> dict[str, object]:
    os2 = font["OS/2"]
    if os2.fsSelection & USE_TYPO_METRICS:
        ascender, descender, line_gap = os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap
    else:
        hhea = font["hhea"]
        ascender, descender, line_gap = hhea.ascent, hhea.descent, hhea.lineGap
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    digits = [hmtx[cmap[ord(d)]][0] for d in "0123456789" if ord(d) in cmap]
    return {
        "unitsPerEm": font["head"].unitsPerEm,
        "ascender": ascender,
        "descender": descender,
        "lineGap": line_gap,
        "digitAdvance": sum(digits) / len(digits) if digits else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("font", type=Path)
    parser.add_argument("--covers", type=Path)
    args = parser.parse_args()
    with TTFont(args.font, lazy=True) as font:
        out = metrics(font)
        if args.covers is not None:
            cmap = font.getBestCmap()
            text = args.covers.read_text(encoding="utf-8")
            out["covered"] = "".join(sorted({c for c in text if ord(c) in cmap}))
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
