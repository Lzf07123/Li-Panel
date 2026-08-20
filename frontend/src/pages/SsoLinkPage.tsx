import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { AuthShell } from "../components/AuthShell";
import { api, ApiError } from "../lib/api";

export function SsoLinkPage() {
  const navigate = useNavigate();
  const [action, setAction] = useState<"bind" | "create">("bind");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [identity, setIdentity] = useState<{ email?: string | null }>({});

  useEffect(() => {
    api
      .ssoLinkStatus()
      .then((status) => {
        if (!status.valid) {
          navigate("/login?error=关联流程无效或已过期", { replace: true });
        } else {
          setIdentity(status);
        }
      })
      .catch(() => navigate("/login", { replace: true }));
  }, [navigate]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await api.ssoLink(action, username, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "关联失败");
    }
  };

  return (
    <AuthShell>
      <p className="mb-4 text-sm text-muted">
        SSO 身份 {identity.email ? `（${identity.email}）` : ""}尚未绑定本地账号，请选择：
      </p>
      <div className="mb-4 grid grid-cols-2 gap-2">
        <button
          type="button"
          className={`btn ${action === "bind" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setAction("bind")}
        >
          绑定已有账号
        </button>
        <button
          type="button"
          className={`btn ${action === "create" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setAction("create")}
        >
          新建账号
        </button>
      </div>
      <form onSubmit={submit} className="space-y-4">
        {error ? <div className="badge badge-danger w-full justify-center py-2">{error}</div> : null}
        <div>
          <label className="label" htmlFor="link-username">用户名</label>
          <input
            id="link-username"
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="link-password">
            {action === "bind" ? "本地账号密码" : "设置密码（至少 8 位）"}
          </label>
          <input
            id="link-password"
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={action === "bind" ? "current-password" : "new-password"}
            required
          />
        </div>
        <button type="submit" className="btn btn-primary w-full">
          {action === "bind" ? "绑定并登录" : "创建并登录"}
        </button>
      </form>
    </AuthShell>
  );
}
