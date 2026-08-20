import { useEffect, useState } from "react";

import { authApi, groupsApi, linksApi, settingsApi } from "../api/client";
import type { GroupOut, LinkOut, MeOut, SiteSettings } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { AsyncButton } from "../components/AsyncButton";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Notice } from "../components/Notice";
import { PageSkeleton } from "../components/PageSkeleton";
import { ScrollTabs } from "../components/ScrollTabs";
import { SiteFooter } from "../components/SiteFooter";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useTheme } from "../hooks/useTheme";
import { useToast } from "../hooks/useToast";
import { formatTags, parseTags } from "../lib/tags";

type Tab = "site" | "manage" | "personal";

const TABS: { key: Tab; label: string }[] = [
  { key: "site", label: "站点信息" },
  { key: "manage", label: "快捷方式" },
  { key: "personal", label: "个人设置" },
];

const emptyLinkForm = {
  id: null as number | null,
  name: "",
  url_lan: "",
  url_wan: "",
  group_id: "",
  description: "",
  is_public: false,
  guest_url_mode: "hidden" as "hidden" | "show",
  tags: [] as string[],
};

export function SettingsPage() {
  const [tab, setTab] = useState<Tab>("site");
  const [me, setMe] = useState<MeOut | null>(null);
  const [site, setSite] = useState<SiteSettings | null>(null);
  const [groups, setGroups] = useState<GroupOut[]>([]);
  const [links, setLinks] = useState<LinkOut[]>([]);
  const [linkMode, setLinkMode] = useState("lan");
  const [linkForm, setLinkForm] = useState(emptyLinkForm);
  const [newGroupName, setNewGroupName] = useState("");
  const [newGroupPublic, setNewGroupPublic] = useState(false);
  const [error, setError] = useState("");
  const [deleteGroupId, setDeleteGroupId] = useState<number | null>(null);
  const [deleteLinkId, setDeleteLinkId] = useState<number | null>(null);
  const [theme, setTheme] = useTheme();
  const toast = useToast();

  useEffect(() => {
    authApi
      .me()
      .then(setMe)
      .catch(() => {
        window.location.href = "/login";
      });
  }, []);

  useEffect(() => {
    if (tab === "site") {
      settingsApi.site().then(setSite).catch(() => setError("加载站点设置失败"));
    }
    if (tab === "manage") {
      Promise.all([groupsApi.list(), linksApi.list()])
        .then(([g, l]) => {
          setGroups(g);
          setLinks(l);
        })
        .catch(() => setError("加载数据失败"));
    }
    if (tab === "personal") {
      settingsApi
        .user()
        .then((settings) => {
          if (settings.link_mode) setLinkMode(settings.link_mode);
        })
        .catch(() => undefined);
    }
  }, [tab]);

  const saveSiteAction = useAsyncAction(
    async (patch: Parameters<typeof settingsApi.updateSite>[0]) => {
      const next = await settingsApi.updateSite(patch);
      setSite(next);
      toast.success("站点信息已保存");
    },
    {
      onError: (err) =>
        setError(err instanceof Error ? err.message : "保存失败"),
    },
  );

  const uploadAction = useAsyncAction(
    async ({ field, file }: { field: "logo" | "favicon"; file: File }) => {
      const { url } = await settingsApi.upload(file);
      setSite((current) => (current ? { ...current, [field]: url } : current));
      toast.success("图片已上传，记得保存");
    },
    {
      onError: (err) =>
        setError(err instanceof Error ? err.message : "上传失败"),
    },
  );

  const addGroupAction = useAsyncAction(async () => {
    await groupsApi.create({
      name: newGroupName.trim(),
      is_public: newGroupPublic,
    });
    setNewGroupName("");
    setNewGroupPublic(false);
    setGroups(await groupsApi.list());
    toast.success("分组已创建");
  });

  const toggleGroupAction = useAsyncAction(
    async (group: GroupOut) => {
      await groupsApi.update(group.id, {
        name: group.name,
        is_public: !group.is_public,
      });
      setGroups(await groupsApi.list());
      toast.success(`「${group.name}」已${group.is_public ? "私密" : "公开"}`);
    },
    { onError: (err) => setError(err.message) },
  );

  const deleteGroupAction = useAsyncAction(
    async (id: number) => {
      await groupsApi.remove(id);
      setGroups(await groupsApi.list());
      toast.success("分组已删除，链接保留为未分组");
      setDeleteGroupId(null);
    },
    { onError: (err) => setError(err.message) },
  );

  const saveLinkAction = useAsyncAction(async () => {
    const body = {
      name: linkForm.name,
      url_lan: linkForm.url_lan,
      url_wan: linkForm.url_wan || null,
      group_id: linkForm.group_id ? Number(linkForm.group_id) : null,
      description: linkForm.description,
      is_public: linkForm.is_public,
      guest_url_mode: linkForm.guest_url_mode,
      tags: linkForm.tags,
    };
    if (linkForm.id === null) {
      await linksApi.create(body);
    } else {
      await linksApi.update(linkForm.id, body);
    }
    setLinkForm(emptyLinkForm);
    setLinks(await linksApi.list());
    toast.success("快捷方式已保存");
  });

  const toggleLinkAction = useAsyncAction(
    async (link: LinkOut) => {
      await linksApi.update(link.id, {
        name: link.name,
        url_lan: link.url_lan,
        is_public: !link.is_public,
        guest_url_mode: link.guest_url_mode,
      });
      setLinks(await linksApi.list());
      toast.success(`「${link.name}」已${link.is_public ? "私密" : "公开"}`);
    },
    { onError: (err) => setError(err.message) },
  );

  const deleteLinkAction = useAsyncAction(
    async (id: number) => {
      await linksApi.remove(id);
      setLinks(await linksApi.list());
      toast.success("快捷方式已删除");
      setDeleteLinkId(null);
    },
    { onError: (err) => setError(err.message) },
  );

  const saveUserAction = useAsyncAction(
    async (patch: Record<string, string>) => {
      await settingsApi.updateUser(patch);
      toast.success("个人设置已保存");
    },
    { onError: (err) => setError(err.message) },
  );

  if (!me) return <PageSkeleton title="管理" />;

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background">
      <div className="relative z-10 flex flex-1 flex-col">
        <AppHeader
          title="管理"
          actions={
            <button
              type="button"
              className="btn btn-ghost h-9 px-3"
              onClick={() => {
                void authApi.logout();
                window.location.href = "/";
              }}
            >
              退出
            </button>
          }
        />
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
          <ScrollTabs fadeColor="var(--lipanel-bg)">
            {TABS.map((item) => (
              <button
                key={item.key}
                type="button"
                role="tab"
                aria-selected={tab === item.key}
                className={`btn h-9 px-4 ${
                  tab === item.key ? "btn-primary" : "btn-ghost"
                }`}
                onClick={() => setTab(item.key)}
              >
                {item.label}
              </button>
            ))}
          </ScrollTabs>
          <div className="mt-6">
            {error ? (
              <div className="mb-4">
                <Notice intent="error">{error}</Notice>
              </div>
            ) : null}

            {tab === "site" && site ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void saveSiteAction.run({
                    site_name: site.site_name,
                    slogan: site.slogan,
                    description: site.description,
                    logo: site.logo,
                    favicon: site.favicon,
                    footer_text: site.footer_text,
                    icp: site.icp,
                    public_mode: site.public_mode === "true",
                  });
                }}
                className="card space-y-4 p-6 sm:p-8"
              >
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block">
                    <span className="label">站点名称</span>
                    <input
                      className="input"
                      value={site.site_name}
                      onChange={(e) =>
                        setSite({ ...site, site_name: e.target.value })
                      }
                    />
                  </label>
                  <label className="block">
                    <span className="label">slogan</span>
                    <input
                      className="input"
                      value={site.slogan}
                      onChange={(e) => setSite({ ...site, slogan: e.target.value })}
                    />
                  </label>
                </div>
                <label className="block">
                  <span className="label">描述</span>
                  <textarea
                    className="input"
                    rows={2}
                    value={site.description}
                    onChange={(e) =>
                      setSite({ ...site, description: e.target.value })
                    }
                  />
                </label>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <span className="label">Logo</span>
                    <div className="flex flex-wrap items-center gap-2">
                      <img
                        src={site.logo}
                        alt=""
                        className="h-10 w-10 rounded-xl bg-surface-2 object-cover"
                      />
                      <input
                        type="file"
                        accept="image/webp,image/png,image/jpeg,image/gif"
                        className="text-sm text-muted file:mr-2 file:rounded-lg file:border-0 file:bg-primary-soft file:px-3 file:py-1.5 file:text-sm file:text-primary"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) void uploadAction.run({ field: "logo", file });
                        }}
                      />
                    </div>
                  </div>
                  <div>
                    <span className="label">favicon</span>
                    <div className="flex flex-wrap items-center gap-2">
                      <img
                        src={site.favicon}
                        alt=""
                        className="h-10 w-10 rounded-xl bg-surface-2 object-cover"
                      />
                      <input
                        type="file"
                        accept="image/webp,image/png,image/jpeg,image/gif"
                        className="text-sm text-muted file:mr-2 file:rounded-lg file:border-0 file:bg-primary-soft file:px-3 file:py-1.5 file:text-sm file:text-primary"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file)
                            void uploadAction.run({ field: "favicon", file });
                        }}
                      />
                    </div>
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block">
                    <span className="label">页脚文案</span>
                    <input
                      className="input"
                      value={site.footer_text}
                      onChange={(e) =>
                        setSite({ ...site, footer_text: e.target.value })
                      }
                    />
                  </label>
                  <label className="block">
                    <span className="label">备案号</span>
                    <input
                      className="input"
                      value={site.icp}
                      onChange={(e) => setSite({ ...site, icp: e.target.value })}
                    />
                  </label>
                </div>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-primary"
                    checked={site.public_mode === "true"}
                    onChange={(e) =>
                      setSite({
                        ...site,
                        public_mode: e.target.checked ? "true" : "false",
                      })
                    }
                  />
                  允许访客查看公开内容
                </label>
                <AsyncButton
                  type="submit"
                  status={saveSiteAction.status}
                  className="btn btn-primary"
                >
                  保存站点信息
                </AsyncButton>
              </form>
            ) : null}

            {tab === "manage" ? (
              <div className="space-y-6">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void addGroupAction.run();
                  }}
                  className="card flex flex-wrap items-end gap-3 p-6"
                >
                  <div className="min-w-48 flex-1">
                    <span className="label">新建分组</span>
                    <input
                      className="input"
                      value={newGroupName}
                      onChange={(e) => setNewGroupName(e.target.value)}
                      placeholder="分组名称"
                      required
                    />
                  </div>
                  <label className="flex cursor-pointer items-center gap-2 pb-2.5 text-sm text-foreground">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-primary"
                      checked={newGroupPublic}
                      onChange={(e) => setNewGroupPublic(e.target.checked)}
                    />
                    公开
                  </label>
                  <AsyncButton
                    type="submit"
                    status={addGroupAction.status}
                    className="btn btn-primary"
                  >
                    创建
                  </AsyncButton>
                </form>

                <div className="card p-6">
                  <h2 className="mb-3 text-sm font-semibold text-foreground">分组</h2>
                  <div className="table-shell overflow-x-auto">
                    <table>
                      <thead>
                        <tr>
                          <th>名称</th>
                          <th>访客可见</th>
                          <th>操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {groups.map((group) => (
                          <tr key={group.id}>
                            <td className="font-medium">{group.name}</td>
                            <td>
                              <span
                                className={`badge ${
                                  group.is_public ? "badge-primary" : "badge-muted"
                                }`}
                              >
                                {group.is_public ? "公开" : "私密"}
                              </span>
                            </td>
                            <td>
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  className="btn btn-ghost h-8 px-3 text-xs"
                                  onClick={() => void toggleGroupAction.run(group)}
                                >
                                  切换可见性
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-danger h-8 px-3 text-xs"
                                  onClick={() => setDeleteGroupId(group.id)}
                                >
                                  删除
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void saveLinkAction.run();
                  }}
                  className="card grid gap-3 p-6 sm:grid-cols-2"
                >
                  <h2 className="text-sm font-semibold text-foreground sm:col-span-2">
                    {linkForm.id === null ? "新建快捷方式" : `编辑：${linkForm.name}`}
                  </h2>
                  <input
                    className="input"
                    placeholder="名称"
                    value={linkForm.name}
                    onChange={(e) => setLinkForm({ ...linkForm, name: e.target.value })}
                    required
                  />
                  <input
                    className="input"
                    placeholder="内网地址 http://…"
                    value={linkForm.url_lan}
                    onChange={(e) =>
                      setLinkForm({ ...linkForm, url_lan: e.target.value })
                    }
                    required
                  />
                  <input
                    className="input"
                    placeholder="公网地址（可选）"
                    value={linkForm.url_wan}
                    onChange={(e) =>
                      setLinkForm({ ...linkForm, url_wan: e.target.value })
                    }
                  />
                  <select
                    className="input"
                    value={linkForm.group_id}
                    onChange={(e) =>
                      setLinkForm({ ...linkForm, group_id: e.target.value })
                    }
                  >
                    <option value="">未分组</option>
                    {groups.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                  <input
                    className="input sm:col-span-2"
                    placeholder="描述（可选）"
                    value={linkForm.description}
                    onChange={(e) =>
                      setLinkForm({ ...linkForm, description: e.target.value })
                    }
                  />
                  <input
                    className="input sm:col-span-2"
                    placeholder="标签，用逗号分隔（最多 8 个）"
                    value={formatTags(linkForm.tags)}
                    onChange={(e) =>
                      setLinkForm({ ...linkForm, tags: parseTags(e.target.value) })
                    }
                  />
                  {linkForm.tags.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5 sm:col-span-2">
                      {linkForm.tags.map((tag) => (
                        <span key={tag} className="badge badge-muted gap-1">
                          {tag}
                          <button
                            type="button"
                            aria-label={`移除标签 ${tag}`}
                            className="text-muted transition-colors hover:text-destructive"
                            onClick={() =>
                              setLinkForm({
                                ...linkForm,
                                tags: linkForm.tags.filter((t) => t !== tag),
                              })
                            }
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-primary"
                      checked={linkForm.is_public}
                      onChange={(e) =>
                        setLinkForm({ ...linkForm, is_public: e.target.checked })
                      }
                    />
                    公开
                  </label>
                  <select
                    className="input"
                    value={linkForm.guest_url_mode}
                    onChange={(e) =>
                      setLinkForm({
                        ...linkForm,
                        guest_url_mode: e.target.value as "hidden" | "show",
                      })
                    }
                  >
                    <option value="hidden">访客隐藏 URL（/go 跳转）</option>
                    <option value="show">访客直接显示 URL</option>
                  </select>
                  <AsyncButton
                    type="submit"
                    status={saveLinkAction.status}
                    className="btn btn-primary sm:col-span-2"
                  >
                    {linkForm.id === null ? "创建" : "保存修改"}
                  </AsyncButton>
                </form>

                <div className="card p-6">
                  <h2 className="mb-3 text-sm font-semibold text-foreground">
                    快捷方式（{links.length}）
                  </h2>
                  <div className="table-shell overflow-x-auto">
                    <table>
                      <thead>
                        <tr>
                          <th>名称</th>
                          <th>内网地址</th>
                          <th>可见性</th>
                          <th>操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {links.map((link) => (
                          <tr key={link.id}>
                            <td className="font-medium">{link.name}</td>
                            <td className="table-cell-clip max-w-56 font-mono text-xs text-muted">
                              {link.url_lan}
                            </td>
                            <td>
                              <span
                                className={`badge ${
                                  link.is_public ? "badge-primary" : "badge-muted"
                                }`}
                              >
                                {link.is_public ? "公开" : "私密"}
                              </span>
                            </td>
                            <td>
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  className="btn btn-ghost h-8 px-3 text-xs"
                                  onClick={() => void toggleLinkAction.run(link)}
                                >
                                  切换
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-ghost h-8 px-3 text-xs"
                                  onClick={() =>
                                    setLinkForm({
                                      id: link.id,
                                      name: link.name,
                                      url_lan: link.url_lan,
                                      url_wan: link.url_wan ?? "",
                                      group_id:
                                        link.group_id == null
                                          ? ""
                                          : String(link.group_id),
                                      description: link.description,
                                      is_public: link.is_public,
                                      guest_url_mode: link.guest_url_mode,
                                      tags: link.tags,
                                    })
                                  }
                                >
                                  编辑
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-danger h-8 px-3 text-xs"
                                  onClick={() => setDeleteLinkId(link.id)}
                                >
                                  删除
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : null}

            {tab === "personal" ? (
              <div className="card max-w-lg space-y-5 p-6">
                <div>
                  <span className="label">主题</span>
                  <select
                    className="input"
                    value={theme}
                    onChange={(e) => {
                      const next = e.target.value as "light" | "dark";
                      setTheme(next);
                      void saveUserAction.run({ theme: next });
                    }}
                  >
                    <option value="light">浅色</option>
                    <option value="dark">深色</option>
                  </select>
                </div>
                <div>
                  <span className="label">链接模式</span>
                  <select
                    className="input"
                    value={linkMode}
                    onChange={(e) => {
                      setLinkMode(e.target.value);
                      void saveUserAction.run({ link_mode: e.target.value });
                    }}
                  >
                    <option value="lan">内网优先</option>
                    <option value="wan">公网优先</option>
                  </select>
                </div>
                <div className="rounded-xl bg-surface-2/60 p-4">
                  <p className="text-sm font-medium text-foreground">SSO 绑定</p>
                  {me.sso.bound ? (
                    <p className="mt-1 text-sm text-muted">
                      已绑定：{me.sso.provider}{" "}
                      {me.sso.email ? `（${me.sso.email}）` : ""}
                    </p>
                  ) : (
                    <p className="mt-1 text-sm text-muted">未绑定</p>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </main>
        <SiteFooter />
      </div>

      <ConfirmDialog
        open={deleteGroupId !== null}
        title="删除分组"
        message="删除后该分组下的快捷方式将保留为「未分组」。"
        confirmLabel="删除"
        status={deleteGroupAction.status}
        onConfirm={() => {
          if (deleteGroupId !== null) void deleteGroupAction.run(deleteGroupId);
        }}
        onCancel={() => setDeleteGroupId(null)}
      />
      <ConfirmDialog
        open={deleteLinkId !== null}
        title="删除快捷方式"
        message="删除后不可恢复。"
        confirmLabel="删除"
        status={deleteLinkAction.status}
        onConfirm={() => {
          if (deleteLinkId !== null) void deleteLinkAction.run(deleteLinkId);
        }}
        onCancel={() => setDeleteLinkId(null)}
      />
    </div>
  );
}
