import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { authApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import { AuthShell } from "../components/AuthShell";
import { Notice } from "../components/Notice";
import { PasswordInput } from "../components/PasswordInput";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

export function SetupPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [ready, setReady] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    authApi
      .setupStatus()
      .then((status) => {
        if (!status.required) {
          navigate("/login", { replace: true });
        } else {
          setReady(true);
        }
      })
      .catch(() => navigate("/login", { replace: true }));
  }, [navigate]);

  const setupAction = useAsyncAction(
    async (name: string, pass: string) => {
      await authApi.createAdmin({ username: name, password: pass });
      toast.success("管理员账号已创建，请登录");
      navigate("/login", { replace: true });
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "初始化失败"),
    },
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await setupAction.run(username, password);
  }

  if (!ready) return null;

  return (
    <AuthShell title="初始化管理员" subtitle="首次启动，请创建管理员账号">
      <form onSubmit={handleSubmit} className="animate-fade-up space-y-4">
        <Notice intent="info">
          用户名 3–32 位字母/数字/_/-，密码至少 8 位。初始化后此入口关闭。
        </Notice>
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
          <span className="label">密码</span>
          <PasswordInput
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input"
            autoComplete="new-password"
            required
          />
        </label>
        <AsyncButton
          type="submit"
          status={setupAction.status}
          className="btn btn-primary w-full"
        >
          创建管理员
        </AsyncButton>
      </form>
    </AuthShell>
  );
}
