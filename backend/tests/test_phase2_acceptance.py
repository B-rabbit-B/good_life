import os
import socket
from datetime import date
from urllib.parse import urlsplit

import pytest

from app.phase2_acceptance import STEP_COUNT, _AcceptanceModel, _MockAmap, run


def test_phase2_acceptance_walks_the_whole_phase_through_the_api():
    env_before = {name: os.environ.get(name) for name in ("AMAP_KEY", "AMAP_BASE_URL", "LLM_ALLOW_PRIVATE_HOSTS")}
    lines = []
    assert run(date.today(), lines.append), "\n".join(lines)
    text = "\n".join(lines)
    assert STEP_COUNT == 23
    assert f"共 {STEP_COUNT} 步，全部通过" in text
    assert text.count("[通过]") == STEP_COUNT and "[未通过]" not in text
    assert "审计里客户端名为 agent 的行共" in text and "nutrition.nearby_restaurants" in text
    assert {name: os.environ.get(name) for name in env_before} == env_before  # 环境变量原样恢复


def _address(base_url: str) -> tuple[str, int]:
    parts = urlsplit(base_url)
    return parts.hostname, parts.port


@pytest.mark.parametrize("server", [lambda: _AcceptanceModel(date.today()), _MockAmap])
def test_mock_servers_free_their_ports_when_stopped(server):
    mock = server()
    mock.start()
    address = _address(mock.base_url)
    with socket.create_connection(address, timeout=2):
        pass
    mock.stop()
    with pytest.raises(OSError):
        socket.create_connection(address, timeout=2)
