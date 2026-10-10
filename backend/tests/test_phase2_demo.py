import socket
from datetime import date
from urllib.parse import urlsplit

import pytest

from app.phase2_demo import _ScriptedModel, run


def test_phase2_demo_walks_chat_tools_and_openings_through_the_api():
    lines = []
    assert run(date.today(), lines.append), "\n".join(lines)
    text = "\n".join(lines)
    assert "共 11 步，全部通过" in text
    assert "客户端名为 agent 的行" in text


def test_scripted_model_frees_its_port_when_stopped():
    model = _ScriptedModel(date.today())
    model.start()
    address = (urlsplit(model.base_url).hostname, urlsplit(model.base_url).port)
    with socket.create_connection(address, timeout=2):
        pass
    model.stop()
    with pytest.raises(OSError):
        socket.create_connection(address, timeout=2)
