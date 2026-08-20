import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { authApi, settingsApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import { AuthShell } from "../components/AuthShell";
import { Notice } from "../components/Notice";
import { PasswordInput } from "../components/PasswordInput";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";
import { useI18n } from "../lib/i18n";
import { APP_NAME } from "../lib/brand";
import { isSafeNext } from "../lib/navigation";
import { getRememberedAccount, persistRememberedAccount } from "../lib/remember";

export function LoginPage() {
  const [searchParams] = useSearchParams();
  const rawNext = searchParams.get("next");
  const next = isSafeNext(rawNext) ? rawNext : null;
  const nextRejected = rawNext !== null && next === null;
  const usernameParam = searchParams.get("username");
  const rememberedAccount = getRememberedAccount();
  const [username, setUsername] = useState(
    usernameParam ?? rememberedAccount ?? "",
  );
  const { t } = useI18n();
  const [password, setPassword] = useState("");
  const [rememberAccount, setRememberAccount] = useState(
    rememberedAccount !== null,
  );
  const [ssoEnabled, setSsoEnabled] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    settingsApi
      .site()
      .then((site) => setSsoEnabled(Boolean(site.oidc_enabled)))
      .catch(() => setSsoEnabled(false));
  }, []);

  const loginAction = useAsyncAction(
    async (
      name: string,
      pass: string,
      remember: boolean,
    ) => {
      await authApi.login({ username: name, password: pass });
      persistRememberedAccount(name, remember);
      if (next) {
        window.location.href = next;
      } else {
        navigate("/");
      }
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "登录失败"),
    },
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await loginAction.run(username, password, rememberAccount);
  }

  return (
    <AuthShell title={`登录 ${APP_NAME}`} subtitle="一次收藏，触达所有常用入口">
      <form onSubmit={handleSubmit} className="animate-fade-up space-y-4">
        {nextRejected ? (
          <Notice intent="warning">
            无法验证返回原网站的链接（域名或协议不一致），登录完成后将停留在面板首页。
          </Notice>
        ) : null}
        <label className="block">
          <span className="label">{t("用户名")}</span>
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
          <span className="label">{t("密码")}</span>
          <PasswordInput
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input"
            autoComplete="current-password"
            required
          />
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            checked={rememberAccount}
            onChange={(e) => setRememberAccount(e.target.checked)}
            className="h-4 w-4 accent-primary"
          />
          {t("记住账号")}
        </label>
        <AsyncButton
          type="submit"
          status={loginAction.status}
          className="btn btn-primary w-full"
        >
          {t("登录")}
        </AsyncButton>
        {ssoEnabled ? (
          <a href="/auth/sso/login" className="btn btn-secondary w-full">
            {t("Li&Pass SSO 登录")}
          </a>
        ) : null}
      </form>
    </AuthShell>
  );
}
