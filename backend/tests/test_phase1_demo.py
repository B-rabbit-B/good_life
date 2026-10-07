from datetime import date

import pytest

from app.phase1_demo import run


@pytest.mark.anyio
async def test_phase1_demo_runs_end_to_end_through_a_real_mcp_process():
    lines = []
    assert await run(date.today(), lines.append), "\n".join(lines)
    text = "\n".join(lines)
    assert "共 10 步，全部通过" in text
    assert "unknown_capability" in text
