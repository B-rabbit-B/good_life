"""第二阶段整体验收的记录、总览与 README。"""

from pathlib import Path

from app.phase2_acceptance import DEMO_USERNAME, STEP_COUNT

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs" / "第二阶段整体验收记录.md"


def test_record_states_the_conditional_pass_and_lists_steps_07_to_10():
    record = RECORD.read_text(encoding="utf-8")
    assert "`" not in record and "uv run" not in record and "python -m" not in record  # 不写代码与命令
    assert "第二阶段整体验收有条件通过" in record
    for row in ("| 07 | 多模型接入 | 有条件通过（", "| 08 | 智能体层 | 有条件通过（", "| 09 | 拍照识别 | 有条件通过（",
                "| 10 | 附近餐厅推荐 | 有条件通过（"):
        assert row in record, row
    assert f"共 {STEP_COUNT} 步，全部通过" in record and DEMO_USERNAME in record
    assert "TOTAL_TESTS" not in record
    pending = record.split("## 五、待补的事项")[1]
    for item in ("步骤 07 第 2 条", "步骤 08 第 1、2、9 条", "步骤 09 第 8 条", "第 1、9 条的真实模型部分",
                 "步骤 10 第 1、2 条", "再走一遍"):
        assert item in pending, item


def test_overview_and_readme_record_the_phase_2_status():
    overview = (ROOT / "docs" / "00-总览与串联.md").read_text(encoding="utf-8")
    assert ("| 第二阶段（07 至 10） | 有条件通过（2026-10-11，Claude 代验；真实模型与真实高德实测待补，"
            "见 第二阶段整体验收记录.md） |" in overview)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "第二阶段（步骤 07 至 10）整体验收已有条件通过" in readme.split("定位声明")[0]
    section = readme.split("## 21. 第二阶段整体验收")[1]
    assert "uv run python -m app.phase2_acceptance" in section and DEMO_USERNAME in section
    assert f"共 {STEP_COUNT} 步" in section and "docs/第二阶段整体验收记录.md" in section
