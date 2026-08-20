import { type FormEvent, useEffect, useState } from "react";

import { AppHeader } from "../components/AppHeader";
import { TechAmbience } from "../components/TechAmbience";
import {
  api,
  ApiError,
  type GroupRow,
  type LinkItem,
  type Me,
  type SiteInfo,
} from "../lib/api";
import { applyTheme, getTheme, type Theme } from "../lib/theme";

type Tab = "site" | "manage" | "personal";

const emptyLinkForm = {
  id: null as number | null,
  name: "",
  url_lan: "",
  url_wan: "",
  group_id: "",
  description: "",
  is_public: false,
  guest_url_mode: "hidden" as "hidden" | "show",
};

export function SettingsPage() {
  const [tab, setTab] = useState<Tab>("site");
  const [me, setMe] = useState<Me | null>(null);
  const [site, setSite] = useState<SiteInfo | null>(null);
  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [links, setLinks] = useState<LinkItem[]>([]);
  const [linkForm, setLinkForm] = useState(emptyLinkForm);
  const [newGroupName, setNewGroupName] = useState("");
  const [newGroupPublic, setNewGroupPublic] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch(() => {
        window.location.href = "/login";
      });
  }, []);

  useEffect(() => {
    if (tab === "site") {
      api.siteSettings().then(setSite).catch(() => setError("加载站点设置失败"));
    }
    if (tab === "manage") {
      Promise.all([api.listGroups(), api.listLinks()])
        .then(([g, l]) => {
          setGroups(g);
          setLinks(l);
        })
        .catch(() => setError("加载数据失败"));
    }
  }, [tab]);

  const flash = (message: string) => {
    setSaved(message);
    window.setTimeout(() => setSaved(""), 2500);
  };

  const saveSite = async (event: FormEvent) => {
    event.preventDefault();
    if (!site) return;
    setError("");
    try {
      const next = await api.updateSiteSettings({
        site_name: site.site_name,
        slogan: site.slogan,
        description: site.description,
        logo: site.logo,
        favicon: site.favicon,
        footer_text: site.footer_text,
        icp: site.icp,
        public_mode: site.public_mode === "true",
      });
      setSite(next);
      flash("站点信息已保存");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    }
  };

  const uploadImage = async (field: "logo" | "favicon", file: File | undefined) => {
    if (!file || !site) return;
    try {
      const { url } = await api.upload(file);
      setSite({ ...site, [field]: url });
      flash("图片已上传，记得保存");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "上传失败");
    }
  };

  const addGroup = async (event: FormEvent) => {
    event.preventDefault();
    if (!newGroupName.trim()) return;
    setError("");
    try {
      await api.createGroup({ name: newGroupName.trim(), is_public: newGroupPublic });
      setNewGroupName("");
      setNewGroupPublic(false);
      setGroups(await api.listGroups());
      flash("分组已创建");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "创建失败");
    }
  };

  const toggleGroup = async (group: GroupRow) => {
    try {
      await api.updateGroup(group.id, { name: group.name, is_public: !group.is_public });
      setGroups(await api.listGroups());
      flash(`「${group.name}」已${!group.is_public ? "公开" : "私密"}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "修改失败");
    }
  };

  const removeGroup = async (id: number) => {
    if (!window.confirm("删除分组？链接将保留为未分组。")) return;
    try {
      await api.deleteGroup(id);
      setGroups(await api.listGroups());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "删除失败");
    }
  };

  const saveLink = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      const body = {
        name: linkForm.name,
        url_lan: linkForm.url_lan,
        url_wan: linkForm.url_wan || null,
        group_id: linkForm.group_id ? Number(linkForm.group_id) : null,
        description: linkForm.description,
        is_public: linkForm.is_public,
        guest_url_mode: linkForm.guest_url_mode,
        tags: [],
      };
      if (linkForm.id === null) {
        await api.createLink(body);
      } else {
        await api.updateLink(linkForm.id, body);
      }
      setLinkForm(emptyLinkForm);
      setLinks(await api.listLinks());
      flash("快捷方式已保存");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    }
  };

  const editLink = (link: LinkItem) => {
    setLinkForm({
      id: link.id,
      name: link.name,
      url_lan: link.url_lan ?? "",
      url_wan: link.url_wan ?? "",
      group_id: link.group_id == null ? "" : String(link.group_id),
      description: link.description,
      is_public: Boolean(link.is_public),
      guest_url_mode: link.guest_url_mode ?? "hidden",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const toggleLinkPublic = async (link: LinkItem) => {
    try {
      await api.updateLink(link.id, {
        name: link.name,
        url_lan: link.url_lan ?? "",
        is_public: !link.is_public,
        guest_url_mode: link.guest_url_mode ?? "hidden",
      });
      setLinks(await api.listLinks());
      flash(`「${link.name}」已${link.is_public ? "私密" : "公开"}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "修改失败");
    }
  };

  const removeLink = async (id: number) => {
    if (!window.confirm("删除该快捷方式？")) return;
    try {
      await api.deleteLink(id);
      setLinks(await api.listLinks());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "删除失败");
    }
  };

  const saveUserSettings = async (patch: Record<string, string>) => {
    try {
      await api.updateUserSettings(patch);
      flash("个人设置已保存");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    }
  };

  return (
    <div className="relative min-h-screen bg-background">
      <TechAmbience />
      <div className="relative z-10">
        <AppHeader username={me?.user.username} />
        <main className="mx-auto max-w-5xl px-4 py-8">
          <div className="mb-6 flex items-center gap-2">
            {(["site", "manage", "personal"] as Tab[]).map((item) => (
              <button
                key={item}
                type="button"
                className={`btn ${tab === item ? "btn-primary" : "btn-ghost"} h-9 px-4`}
                onClick={() => setTab(item)}
              >
                {item === "site" ? "站点信息" : item === "manage" ? "快捷方式" : "个人设置"}
              </button>
            ))}
          </div>
          {error ? <div className="badge badge-danger mb-4 w-full justify-center py-2">{error}</div> : null}
          {saved ? <div className="badge badge-success mb-4 w-full justify-center py-2">{saved}</div> : null}

          {tab === "site" && site ? (
            <form onSubmit={saveSite} className="card space-y-4 p-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="label">站点名称</label>
                  <input
                    className="input"
                    value={site.site_name}
                    onChange={(e) => setSite({ ...site, site_name: e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">slogan</label>
                  <input
                    className="input"
                    value={site.slogan}
                    onChange={(e) => setSite({ ...site, slogan: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className="label">描述</label>
                <textarea
                  className="input"
                  rows={2}
                  value={site.description}
                  onChange={(e) => setSite({ ...site, description: e.target.value })}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="label">Logo</label>
                  <div className="flex items-center gap-2">
                    <img src={site.logo} alt="" className="h-10 w-10 rounded-xl bg-surface-2 object-cover" />
                    <input
                      type="file"
                      accept="image/webp,image/png,image/jpeg,image/gif"
                      className="text-sm text-muted file:mr-2 file:rounded-lg file:border-0 file:bg-primary-soft file:px-3 file:py-1.5 file:text-sm file:text-primary"
                      onChange={(e) => void uploadImage("logo", e.target.files?.[0])}
                    />
                  </div>
                </div>
                <div>
                  <label className="label">favicon</label>
                  <div className="flex items-center gap-2">
                    <img src={site.favicon} alt="" className="h-10 w-10 rounded-xl bg-surface-2 object-cover" />
                    <input
                      type="file"
                      accept="image/webp,image/png,image/jpeg,image/gif"
                      className="text-sm text-muted file:mr-2 file:rounded-lg file:border-0 file:bg-primary-soft file:px-3 file:py-1.5 file:text-sm file:text-primary"
                      onChange={(e) => void uploadImage("favicon", e.target.files?.[0])}
                    />
                  </div>
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="label">页脚文案</label>
                  <input
                    className="input"
                    value={site.footer_text}
                    onChange={(e) => setSite({ ...site, footer_text: e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">备案号</label>
                  <input
                    className="input"
                    value={site.icp}
                    onChange={(e) => setSite({ ...site, icp: e.target.value })}
                  />
                </div>
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-[var(--lipanel-primary)]"
                  checked={site.public_mode === "true"}
                  onChange={(e) => setSite({ ...site, public_mode: e.target.checked ? "true" : "false" })}
                />
                允许访客查看公开内容
              </label>
              <button type="submit" className="btn btn-primary">保存站点信息</button>
            </form>
          ) : null}

          {tab === "manage" ? (
            <div className="space-y-6">
              <form onSubmit={addGroup} className="card flex flex-wrap items-end gap-3 p-6">
                <div className="min-w-48 flex-1">
                  <label className="label">新建分组</label>
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
                    className="h-4 w-4 accent-[var(--lipanel-primary)]"
                    checked={newGroupPublic}
                    onChange={(e) => setNewGroupPublic(e.target.checked)}
                  />
                  公开
                </label>
                <button type="submit" className="btn btn-primary">创建</button>
              </form>

              <div className="card p-6">
                <h2 className="mb-3 text-sm font-semibold text-foreground">分组</h2>
                <ul className="space-y-2">
                  {groups.map((group) => (
                    <li key={group.id} className="flex items-center gap-2 rounded-xl bg-surface-2/60 px-3 py-2">
                      <span className="min-w-0 flex-1 truncate text-sm text-foreground">{group.name}</span>
                      <button
                        type="button"
                        className="btn btn-ghost h-8 px-3 text-xs"
                        onClick={() => void toggleGroup(group)}
                      >
                        {group.is_public ? "公开" : "私密"}（点击切换）
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger h-8 px-3 text-xs"
                        onClick={() => void removeGroup(group.id)}
                      >
                        删除
                      </button>
                    </li>
                  ))}
                </ul>
              </div>

              <form onSubmit={saveLink} className="card grid gap-3 p-6 sm:grid-cols-2">
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
                  onChange={(e) => setLinkForm({ ...linkForm, url_lan: e.target.value })}
                  required
                />
                <input
                  className="input"
                  placeholder="公网地址（可选）"
                  value={linkForm.url_wan}
                  onChange={(e) => setLinkForm({ ...linkForm, url_wan: e.target.value })}
                />
                <select
                  className="input"
                  value={linkForm.group_id}
                  onChange={(e) => setLinkForm({ ...linkForm, group_id: e.target.value })}
                >
                  <option value="">未分组</option>
                  {groups.map((group) => (
                    <option key={group.id} value={group.id}>{group.name}</option>
                  ))}
                </select>
                <input
                  className="input sm:col-span-2"
                  placeholder="描述（可选）"
                  value={linkForm.description}
                  onChange={(e) => setLinkForm({ ...linkForm, description: e.target.value })}
                />
                <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-[var(--lipanel-primary)]"
                    checked={linkForm.is_public}
                    onChange={(e) => setLinkForm({ ...linkForm, is_public: e.target.checked })}
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
                <button type="submit" className="btn btn-primary sm:col-span-2">
                  {linkForm.id === null ? "创建" : "保存修改"}
                </button>
              </form>

              <div className="card p-6">
                <h2 className="mb-3 text-sm font-semibold text-foreground">快捷方式（{links.length}）</h2>
                <ul className="space-y-2">
                  {links.map((link) => (
                    <li key={link.id} className="flex flex-wrap items-center gap-2 rounded-xl bg-surface-2/60 px-3 py-2">
                      <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                        {link.name}
                        <span className="ml-2 text-xs text-muted">{link.url_lan}</span>
                      </span>
                      <button
                        type="button"
                        className="btn btn-ghost h-8 px-3 text-xs"
                        onClick={() => void toggleLinkPublic(link)}
                      >
                        {link.is_public ? "公开" : "私密"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost h-8 px-3 text-xs"
                        onClick={() => editLink(link)}
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger h-8 px-3 text-xs"
                        onClick={() => void removeLink(link.id)}
                      >
                        删除
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}

          {tab === "personal" ? (
            <div className="card max-w-lg space-y-5 p-6">
              <div>
                <label className="label">主题</label>
                <select
                  className="input"
                  value={getTheme()}
                  onChange={(e) => {
                    const theme = e.target.value as Theme;
                    applyTheme(theme);
                    void saveUserSettings({ theme });
                  }}
                >
                  <option value="system">跟随系统</option>
                  <option value="light">浅色</option>
                  <option value="dark">深色</option>
                </select>
              </div>
              <div>
                <label className="label">链接模式</label>
                <select
                  className="input"
                  defaultValue="lan"
                  onChange={(e) => void saveUserSettings({ link_mode: e.target.value })}
                >
                  <option value="lan">内网优先</option>
                  <option value="wan">公网优先</option>
                </select>
              </div>
              <div className="rounded-xl bg-surface-2/60 p-4">
                <p className="text-sm font-medium text-foreground">SSO 绑定</p>
                {me?.sso.bound ? (
                  <p className="mt-1 text-sm text-muted">
                    已绑定：{me.sso.provider} {me.sso.email ? `（${me.sso.email}）` : ""}
                  </p>
                ) : (
                  <p className="mt-1 text-sm text-muted">未绑定</p>
                )}
              </div>
            </div>
          ) : null}
        </main>
      </div>
    </div>
  );
}
