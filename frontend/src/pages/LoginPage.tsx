import { type FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { AuthShell } from "../components/AuthShell";
import { api, ApiError } from "../lib/api";

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [ssoEnabled, setSsoEnabled] = useState(false);

  useEffect(() => {
    api
      .siteSettings()
      .then((site) => setSsoEnabled(Boolean(site.oidc_enabled)))
      .catch(() => setSsoEnabled(false));
    const serverError = params.get("error");
    if (serverError) {
      setError(decodeURIComponent(serverError));
    }
  }, [params]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await api.login(username, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "登录失败");
    }
  };

  return (
    <AuthShell>
      <form onSubmit={submit} className="space-y-4">
        {error ? <div className="badge badge-danger w-full justify-center py-2">{error}</div> : null}
        <div>
          <label className="label" htmlFor="username">用户名</label>
          <input
            id="username"
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="password">密码</label>
          <input
            id="password"
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        <button type="submit" className="btn btn-primary w-full">登录</button>
      </form>
      {ssoEnabled ? (
        <a href="/auth/sso/login" className="btn btn-secondary mt-3 w-full">
          Li&Pass SSO 登录
        </a>
      ) : null}
    </AuthShell>
  );
}
