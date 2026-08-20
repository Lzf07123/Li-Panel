from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from urllib.parse import quote, urlencode, urlparse

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app import oidc
from app.db import create_user, get_db, get_user_by_username
from app.deps import current_user
from app.routers.setup import validate_username
from app.security import create_session, delete_session, hash_password, new_token, verify_password

router = APIRouter(tags=["sso"])


class UnbindIn(BaseModel):
    password: str


def _safe_logout_redirect(value: str, settings) -> str:
    """回跳白名单：环境变量 PANEL_SSO_LOGOUT_REDIRECTS；为空仅允许站内相对路径。"""
    if value.startswith("/") and not value.startswith("//"):
        return value
    if value in settings.sso_logout_redirects:
        return value
    return "/"


@router.post("/auth/sso/backchannel")
async def sso_backchannel(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """回程登出：logout_token 验签后按 sub+sid 精确下线会话。"""
    from app.oidc import OIDCError, OIDCClient

    settings = request.app.state.settings
    if not settings.oidc_enabled or not (
        settings.oidc_issuer
        and settings.oidc_client_id
        and settings.oidc_redirect_uri
    ):
        raise HTTPException(status_code=400, detail="OIDC 未启用")
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        payload = await request.json()
        token = payload.get("logout_token") if isinstance(payload, dict) else None
    else:
        form = await request.form()
        token = form.get("logout_token")
    if not token:
        raise HTTPException(status_code=400, detail="缺少 logout_token")
    try:
        claims = OIDCClient(settings).validate_logout_token(token)
    except OIDCError as exc:
        raise HTTPException(status_code=401, detail=exc.message)
    sid = claims.get("sid")
    sub = claims.get("sub")
    if not sid:
        raise HTTPException(status_code=400, detail="缺少 sid")
    conn.execute(
        "DELETE FROM sessions WHERE sso_sid = ? AND user_id IN "
        "(SELECT user_id FROM sso_identities WHERE subject = ?)",
        (sid, sub),
    )
    return {"ok": True}


@router.get("/auth/sso/logout")
def sso_logout(
    request: Request,
    lipanel_session: Annotated[str | None, Cookie()] = None,
    conn: sqlite3.Connection = Depends(get_db),
    redirect_after: str = "/",
) -> RedirectResponse:
    """RP 发起登出：本地会话注销 + IdP end_session_endpoint（id_token_hint）+ 回跳白名单。"""
    settings = request.app.state.settings
    target = _safe_logout_redirect(redirect_after, settings)

    id_token: str | None = None
    if lipanel_session:
        row = conn.execute(
            "SELECT sso_id_token FROM sessions WHERE token = ?", (lipanel_session,)
        ).fetchone()
        if row is not None:
            id_token = row["sso_id_token"]
        delete_session(conn, lipanel_session)

    if not settings.oidc_enabled or not (
        settings.oidc_issuer
        and settings.oidc_client_id
        and settings.oidc_redirect_uri
    ):
        return RedirectResponse(target, status_code=302)

    try:
        from app.oidc import OIDCClient

        discovery = OIDCClient(settings).discover()
        end_session = discovery.get("end_session_endpoint")
        if not end_session:
            return RedirectResponse(target, status_code=302)
        params: dict[str, str] = {"post_logout_redirect_uri": target}
        if id_token:
            params["id_token_hint"] = id_token
        return RedirectResponse(end_session + "?" + urlencode(params), status_code=302)
    except Exception:
        return RedirectResponse(target, status_code=302)


@router.get("/api/sso/status")
def sso_status(
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute(
        "SELECT provider, email, nickname FROM sso_identities WHERE user_id = ?",
        (user["id"],),
    ).fetchone()
    if row is None:
        return {"bound": False, "provider": None, "email": None, "nickname": None}
    return {
        "bound": True,
        "provider": row["provider"],
        "email": row["email"],
        "nickname": row["nickname"],
    }


@router.delete("/api/sso/identity")
def sso_unbind(
    body: UnbindIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """解绑 SSO：需本地密码确认；只删身份，不删本地账号。"""
    row = conn.execute(
        "SELECT id FROM sso_identities WHERE user_id = ?", (user["id"],)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=400, detail="当前账号未绑定 SSO")
    from app.security import verify_password

    if not verify_password(body.password, user["password_hash"], user["salt"]):
        raise HTTPException(status_code=403, detail="本地密码错误")
    conn.execute("DELETE FROM sso_identities WHERE id = ?", (row["id"],))
    return {"ok": True}

FLOW_MINUTES = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _valid_flow(
    conn: sqlite3.Connection, token: str | None
) -> sqlite3.Row | None:
    if not token:
        return None
    return conn.execute(
        "SELECT * FROM sso_flows WHERE token = ? AND consumed = 0 AND expires_at > ?",
        (token, _fmt(_now())),
    ).fetchone()


def _sso_error_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(f"/login?error={quote(message)}", status_code=302)


@router.get("/auth/sso/login")
def sso_login(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    settings = request.app.state.settings
    if not settings.oidc_enabled:
        raise HTTPException(status_code=404, detail="SSO 未启用")
    client = oidc.OIDCClient(settings)
    state, nonce = new_token(16), new_token(16)
    verifier, challenge = oidc.generate_pkce()
    flow_token = new_token()
    expires = _now() + timedelta(minutes=FLOW_MINUTES)
    try:
        url = client.authorize_url(state, nonce, challenge)
    except oidc.OIDCError as exc:
        return _sso_error_redirect(exc.message)
    conn.execute(
        "INSERT INTO sso_flows (token, state, nonce, code_verifier, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (flow_token, state, nonce, verifier, _fmt(expires)),
    )
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        "lipanel_sso_flow",
        flow_token,
        max_age=FLOW_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return response


@router.get("/auth/sso/callback")
def sso_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    lipanel_sso_flow: Annotated[str | None, Cookie()] = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    if error:
        message = (
            "账号已被该网站封禁"
            if error_description == "account_blocked"
            else "授权被拒绝"
        )
        return _sso_error_redirect(message)
    flow = _valid_flow(conn, lipanel_sso_flow)
    if flow is None or state is None or flow["state"] != state or not code:
        return _sso_error_redirect("授权流程无效或已过期，请重新登录")

    settings = request.app.state.settings
    if not request.app.state.sso_limiter.allow(
        request.client.host if request.client else "unknown"
    ):
        return _sso_error_redirect("请求过于频繁，请稍后再试")
    client = oidc.OIDCClient(settings)
    try:
        tokens = client.exchange(code, flow["code_verifier"])
        jwks = client.jwks()
        claims = client.validate_id_token(
            tokens["id_token"], flow["nonce"], tokens["access_token"], jwks
        )
        info = client.userinfo(tokens["access_token"])
    except oidc.OIDCError as exc:
        return _sso_error_redirect(exc.message)

    subject = claims.get("sub") or info.get("sub")
    if not subject:
        return _sso_error_redirect("身份信息缺失")

    identity = conn.execute(
        "SELECT * FROM sso_identities WHERE provider = 'lipass' AND subject = ?",
        (subject,),
    ).fetchone()
    if identity is not None:
        conn.execute(
            "UPDATE sso_identities SET email = ?, nickname = ?, avatar = ?, "
            "last_login_at = ? WHERE id = ?",
            (
                info.get("email"),
                info.get("nickname"),
                info.get("picture"),
                _fmt(_now()),
                identity["id"],
            ),
        )
        conn.execute("UPDATE sso_flows SET consumed = 1 WHERE id = ?", (flow["id"],))
        session_token = create_session(
            conn,
            identity["user_id"],
            sso_sid=claims.get("sid"),
            sso_id_token=tokens.get("id_token"),
            session_days=settings.session_days,
        )
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(
            "lipanel_session",
            session_token,
            max_age=settings.session_days * 86400,
            httponly=True,
            samesite="lax",
            secure=settings.cookie_secure,
            path="/",
        )
        return response

    conn.execute(
        "UPDATE sso_flows SET subject = ?, sid = ?, email = ?, nickname = ?, avatar = ? "
        "WHERE id = ?",
        (
            subject,
            claims.get("sid"),
            info.get("email"),
            info.get("nickname"),
            info.get("picture"),
            flow["id"],
        ),
    )
    return RedirectResponse("/sso/link", status_code=302)


@router.get("/auth/sso/link")
def sso_link_page(
    lipanel_sso_flow: Annotated[str | None, Cookie()] = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    flow = _valid_flow(conn, lipanel_sso_flow)
    if flow is None or not flow["subject"]:
        return _sso_error_redirect("关联流程无效或已过期")
    return RedirectResponse("/sso/link", status_code=302)


@router.get("/api/sso/link-status")
def sso_link_status(
    lipanel_sso_flow: Annotated[str | None, Cookie()] = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    flow = _valid_flow(conn, lipanel_sso_flow)
    if flow is None or not flow["subject"]:
        return {"valid": False}
    return {
        "valid": True,
        "email": flow["email"],
        "nickname": flow["nickname"],
    }


class LinkIn(BaseModel):
    action: Literal["bind", "create"]
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@router.post("/api/sso/link")
def sso_link(
    body: LinkIn,
    request: Request,
    lipanel_sso_flow: Annotated[str | None, Cookie()] = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    flow = _valid_flow(conn, lipanel_sso_flow)
    if flow is None or not flow["subject"]:
        raise HTTPException(status_code=409, detail="关联流程无效或已过期")
    exists = conn.execute(
        "SELECT id FROM sso_identities WHERE provider = 'lipass' AND subject = ?",
        (flow["subject"],),
    ).fetchone()
    if exists:
        raise HTTPException(status_code=409, detail="该 SSO 身份已绑定账号")

    settings = request.app.state.settings
    if body.action == "bind":
        user = get_user_by_username(conn, body.username)
        if user is None or not verify_password(
            body.password, user["password_hash"], user["salt"]
        ):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        user_id = user["id"]
        status = 200
    else:
        validate_username(body.username)
        if len(body.password) < 8:
            raise HTTPException(status_code=422, detail="密码至少 8 位")
        if get_user_by_username(conn, body.username):
            raise HTTPException(status_code=409, detail="用户名已存在")
        password_hash, salt = hash_password(body.password)
        user_id = create_user(conn, body.username, password_hash, salt, role="user")
        status = 201

    conn.execute(
        "INSERT INTO sso_identities (user_id, provider, subject, email, nickname, avatar, last_login_at) "
        "VALUES (?, 'lipass', ?, ?, ?, ?, ?)",
        (
            user_id,
            flow["subject"],
            flow["email"],
            flow["nickname"],
            flow["avatar"],
            _fmt(_now()),
        ),
    )
    conn.execute("UPDATE sso_flows SET consumed = 1 WHERE id = ?", (flow["id"],))
    session_token = create_session(
        conn, user_id, sso_sid=flow["sid"], session_days=settings.session_days
    )
    response = JSONResponse(status_code=status, content={"ok": True})
    response.set_cookie(
        "lipanel_session",
        session_token,
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return response


@router.get("/auth/logout")
def logout_uri(
    request: Request,
    next: str | None = None,
    lipanel_session: Annotated[str | None, Cookie()] = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    if lipanel_session:
        delete_session(conn, lipanel_session)
    target = next or "/"
    parsed = urlparse(target)
    host = request.headers.get("host", "").split(":")[0]
    if target.startswith("//") or parsed.scheme not in {"", "http", "https"}:
        target = "/"
    elif parsed.netloc and parsed.hostname != host:
        target = "/"
    response = RedirectResponse(target, status_code=302)
    response.delete_cookie("lipanel_session", path="/")
    return response
