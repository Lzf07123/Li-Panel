from __future__ import annotations


def test_panel_health_fields_logged_in_only(client, auth_headers):
    """/api/panel 下发 health_* 字段供客户端存活探测；访客公开视图不下发（隐私）。"""
    client.post(
        "/api/links",
        json={
            "name": "探测目标",
            "url_lan": "https://example.com",
            "is_public": True,
            "health_enabled": True,
            "health_interval": 30,
            "health_timeout": 8,
            "health_threshold": 2,
        },
        headers=auth_headers,
    )
    panel = client.get("/api/panel", headers=auth_headers).json()
    link = panel["ungrouped"][0]
    assert link["health_enabled"] is True
    assert link["health_interval"] == 30
    assert link["health_timeout"] == 8
    assert link["health_threshold"] == 2

    # 访客公开视图不暴露健康检查配置与内网地址
    client.cookies.clear()
    public_panel = client.get("/api/panel").json()
    public_link = public_panel["ungrouped"][0]
    assert "health_enabled" not in public_link
    assert "health_interval" not in public_link
    assert "url_lan" not in public_link
