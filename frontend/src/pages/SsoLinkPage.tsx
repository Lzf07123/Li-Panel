import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { authApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import { AuthShell } from "../components/AuthShell";
import { Notice } from "../components/Notice";
import { PasswordInput } from "../components/PasswordInput";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

type Action = "bind" | "create";

export function SsoLinkPage() {
  const [action, setAction] = useState<Action>("bind");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [identity, setIdentity] = useState<{
    valid: boolean;
    email?: string | null;
  }>({ valid: false });
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    authApi
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

  const linkAction = useAsyncAction(
    async (act: Action, name: string, pass: string) => {
      await authApi.ssoLink({ action: act, username: name, password: pass });
      toast.success("已关联 SSO 身份并登录");
      navigate("/", { replace: true });
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "关联失败"),
    },
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await linkAction.run(action, username, password);
  }

  if (!identity.valid) return null;

  return (
    <AuthShell title="关联 SSO 身份" subtitle="绑定已有账号，或创建新账号">
      <form onSubmit={handleSubmit} className="animate-fade-up space-y-4">
        <Notice intent="info">
          SSO 身份{identity.email ? `（${identity.email}）` : ""}尚未绑定本地账号。
          绑定已有账号需验证本地密码，防止身份被他人占用。
        </Notice>
        <div className="grid grid-cols-2 gap-2">
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
        <label className="block">
          <span className="label">用户名</span>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="input"
            autoComplete="username"
            required
          />
        </label>
        <label className="block">
          <span className="label">
            {action === "bind" ? "本地账号密码" : "设置密码（至少 8 位）"}
          </span>
          <PasswordInput
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input"
            autoComplete={action === "bind" ? "current-password" : "new-password"}
            required
          />
        </label>
        <AsyncButton
          type="submit"
          status={linkAction.status}
          className="btn btn-primary w-full"
        >
          {action === "bind" ? "绑定并登录" : "创建并登录"}
        </AsyncButton>
      </form>
    </AuthShell>
  );
}
