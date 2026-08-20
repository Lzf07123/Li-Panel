"""状态变化通知：向 ntfy/Webhook URL POST JSON，失败静默不影响主流程。"""
from __future__ import annotations

import httpx


def send_notification(url: str, payload: dict, timeout: float = 5.0) -> None:
    if not url:
        return
    try:
        httpx.post(
            url,
            json=payload,
            timeout=timeout,
            headers={"User-Agent": "LiPanel/1.0"},
        )
    except httpx.HTTPError:
        pass
