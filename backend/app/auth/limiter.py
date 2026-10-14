"""登录与密码复核的失败次数限制：同一个键在 15 分钟内失败 5 次后，再尝试（即使密码正确）一律 429。

进程内滑动窗口计数（写法同 restaurants/service.py），只在单进程部署下有效；多个进程或多台机器之间不共享，
重启后清零。键由调用方给出：登录用“name:用户名”，密码复核用“user:用户编号”。
"""

import threading
import time
from collections import deque

from app.errors import AppError

MAX_FAILURES = 5
WINDOW_SECONDS = 900.0

_lock = threading.Lock()
_failures: dict[str, deque[float]] = {}


def _prune(now: float) -> None:
    """清掉窗口已过的失败记录与空键，字典不会只增不减。调用方持有锁。"""
    for key in list(_failures):
        recent = _failures[key]
        while recent and now - recent[0] >= WINDOW_SECONDS:
            recent.popleft()
        if not recent:
            del _failures[key]


def check(key: str) -> None:
    """窗口内已失败 MAX_FAILURES 次时抛 429 too_many_attempts。"""
    with _lock:
        _prune(time.monotonic())
        if len(_failures.get(key, ())) >= MAX_FAILURES:
            raise AppError(429, "too_many_attempts", "尝试次数过多，请 15 分钟后再试")


def record_failure(key: str) -> None:
    with _lock:
        _failures.setdefault(key, deque()).append(time.monotonic())


def reset(key: str) -> None:
    """成功后清零。"""
    with _lock:
        _failures.pop(key, None)


def reset_all() -> None:
    """清空全部计数（测试用）。"""
    with _lock:
        _failures.clear()
