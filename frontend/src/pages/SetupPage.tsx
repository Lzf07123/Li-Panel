import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { AuthShell } from "../components/AuthShell";
import { api, ApiError } from "../lib/api";

export function SetupPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.setupStatus().then((status) => {
      if (!status.required) {
        navigate("/login", { replace: true });
      }
    });
  }, [navigate]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await api.createAdmin(username, password);
      navigate("/login", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "初始化失败");
    }
  };

  return (
    <AuthShell>
      <p className="mb-4 text-sm text-muted">首次启动，请创建管理员账号。</p>
      <form onSubmit={submit} className="space-y-4">
        {error ? <div className="badge badge-danger w-full justify-center py-2">{error}</div> : null}
        <div>
          <label className="label" htmlFor="setup-username">用户名</label>
          <input
            id="setup-username"
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="setup-password">密码（至少 8 位）</label>
          <input
            id="setup-password"
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
        </div>
        <button type="submit" className="btn btn-primary w-full">创建管理员</button>
      </form>
    </AuthShell>
  );
}
