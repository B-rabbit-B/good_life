import os
import socket
from datetime import date
from urllib.parse import urlsplit

import pytest

from app import phase2_acceptance
from app.config import get_settings
from app.phase2_acceptance import STEP_COUNT, _AcceptanceModel, _MockAmap, run

ENV_NAMES = ("AMAP_KEY", "AMAP_BASE_URL", "LLM_ALLOW_PRIVATE_HOSTS")


def _snapshot() -> tuple[dict, tuple]:
    settings = get_settings()
    return {name: os.environ.get(name) for name in ENV_NAMES}, (settings.amap_key, settings.amap_base_url)


def _address(base_url: str) -> tuple[str, int]:
    parts = urlsplit(base_url)
    return parts.hostname, parts.port


def _assert_closed(base_url: str) -> None:
    with pytest.raises(OSError):
        socket.create_connection(_address(base_url), timeout=2)


def test_phase2_acceptance_walks_the_whole_phase_through_the_api():
    before = _snapshot()
    lines = []
    assert run(date.today(), lines.append), "\n".join(lines)
    text = "\n".join(lines)
    assert STEP_COUNT == 23
    assert f"共 {STEP_COUNT} 步，全部通过" in text
    assert text.count("[通过]") == STEP_COUNT and "[未通过]" not in text
    assert "审计里客户端名为 agent 的行共" in text and "nutrition.nearby_restaurants" in text
    assert _snapshot() == before  # 环境变量与配置（高德密钥与地址）原样恢复


@pytest.fixture
def servers(monkeypatch):
    """记下这次运行启动的两个模拟服务。"""
    started = []

    class Model(_AcceptanceModel):
        def start(self):
            super().start()
            started.append(self)

    class Amap(_MockAmap):
        def start(self):
            super().start()
            started.append(self)

    monkeypatch.setattr(phase2_acceptance, "_AcceptanceModel", Model)
    monkeypatch.setattr(phase2_acceptance, "_MockAmap", Amap)
    return started


def test_a_failure_mid_way_is_reported_and_everything_is_restored(monkeypatch, servers):
    def broken(story):
        raise RuntimeError("演示用的故障")

    monkeypatch.setattr(phase2_acceptance, "photo_steps", broken)  # 中期检查的 9 步走完之后出错
    before = _snapshot()
    lines = []
    assert run(date.today(), lines.append) is False
    text = "\n".join(lines)
    assert "[未通过] 验收中断" in text and "演示用的故障" in text
    assert text.count("[通过]") == 9
    assert f"共 10 步（应为 {STEP_COUNT} 步），其中 1 步未通过" in text
    assert _snapshot() == before
    assert len(servers) == 2
    for server in servers:
        _assert_closed(server.base_url)


def test_env_is_restored_even_if_stopping_a_server_fails(monkeypatch, servers):
    def broken(story):
        raise RuntimeError("演示用的故障")

    def failing_stop(self):
        raise OSError("关不掉")

    monkeypatch.setattr(phase2_acceptance, "chat_steps", broken)
    monkeypatch.setattr(phase2_acceptance._AcceptanceModel, "stop", failing_stop)
    before = _snapshot()
    with pytest.raises(OSError, match="关不掉"):
        run(date.today(), lambda line: None)
    assert _snapshot() == before
    model, amap = servers
    _assert_closed(amap.base_url)  # 模型关不掉时，高德模拟服务照样关闭
    _AcceptanceModel.stop(model)  # 用原来的方法收尾
    _assert_closed(model.base_url)


@pytest.mark.parametrize("server", [lambda: _AcceptanceModel(date.today()), _MockAmap])
def test_mock_servers_free_their_ports_when_stopped(server):
    mock = server()
    mock.start()
    address = _address(mock.base_url)
    with socket.create_connection(address, timeout=2):
        pass
    mock.stop()
    _assert_closed(mock.base_url)
