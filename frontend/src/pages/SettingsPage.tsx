import { useEffect, useState } from "react";

import { authApi, backupApi, groupsApi, linksApi, rssApi, sessionsApi, settingsApi, ssoApi, tagsApi } from "../api/client";
import type { GroupOut, LinkOut, MeOut, SiteSettings } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { AsyncButton } from "../components/AsyncButton";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Notice } from "../components/Notice";
import { PasswordInput } from "../components/PasswordInput";
import { PageSkeleton } from "../components/PageSkeleton";
import { ScrollTabs } from "../components/ScrollTabs";
import { SiteFooter } from "../components/SiteFooter";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useTheme } from "../hooks/useTheme";
import { useI18n, type Lang } from "../lib/i18n";
import { useToast } from "../hooks/useToast";
import { GROUP_ICON_NAMES, isGroupIconName } from "../components/GroupIcon";
import type { GroupIconName } from "../components/GroupIcon";
import { formatTags, parseTags } from "../lib/tags";
import {
  APP_VERSION,
  ICP_FILING_ICON_ENV,
  ICP_FILING_TEXT_ENV,
  ICP_FILING_URL_ENV,
  POLICE_FILING_ICON_ENV,
  POLICE_FILING_TEXT_ENV,
  POLICE_FILING_URL_ENV,
} from "../lib/brand";

type Tab = "site" | "manage" | "tags" | "personal";

const TABS: { key: Tab; label: string }[] = [
  { key: "site", label: "站点信息" },
  { key: "manage", label: "快捷方式" },
  { key: "tags", label: "标签管理" },
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
  open_mode: "new_tab" as "new_tab" | "modal",
  tags: [] as string[],
  health_enabled: true,
  health_interval: 10,
  health_timeout: 5,
  health_threshold: 1,
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
  const [newGroupIcon, setNewGroupIcon] = useState<GroupIconName>("folder");
  const [error, setError] = useState("");
  const [deleteGroupId, setDeleteGroupId] = useState<number | null>(null);
  const [deleteLinkId, setDeleteLinkId] = useState<number | null>(null);
  const [groupDragId, setGroupDragId] = useState<number | null>(null);
  const [groupDragOverId, setGroupDragOverId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchTargetGroup, setBatchTargetGroup] = useState("");
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false);
  const [tags, setTags] = useState<{ name: string; count: number }[]>([]);
  const [editingTag, setEditingTag] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteTagName, setDeleteTagName] = useState<string | null>(null);
  const [duplicateNotice, setDuplicateNotice] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<
    {
      name: string;
      created_at?: string;
      groups: number;
      links: number;
      settings: number;
      site_settings: number;
    }[]
  >([]);
  const [restoreName, setRestoreName] = useState<string | null>(null);
  const [rssUrls, setRssUrls] = useState<string[]>(["", "", ""]);
  const [unbindOpen, setUnbindOpen] = useState(false);
  const [unbindPassword, setUnbindPassword] = useState("");
  const [sessions, setSessions] = useState<
    {
      id: number;
      created_at: string;
      last_used_at: string | null;
      expires_at: string;
      current: boolean;
    }[]
  >([]);
  const [theme, setTheme] = useTheme();
  const toast = useToast();
  const { t, lang, setLang } = useI18n();
  const handleLangChange = (next: Lang) => {
    setLang(next);
    document.documentElement.lang = next;
    void settingsApi.updateUser({ lang: next }).catch(() => undefined);
  };
  const isAdmin = me?.user.role === "admin";
  const visibleTabs = TABS.filter((item) => item.key !== "site" || isAdmin);
  // 构建期显式配置的备案环境变量：非空即优先，后台修改不生效
  const filingEnvOverrides = [
    { name: "VITE_ICP_FILING_TEXT", label: t("备案号"), value: ICP_FILING_TEXT_ENV },
    { name: "VITE_ICP_FILING_URL", label: t("备案链接"), value: ICP_FILING_URL_ENV },
    { name: "VITE_ICP_FILING_ICON", label: t("备案图标"), value: ICP_FILING_ICON_ENV },
    { name: "VITE_POLICE_FILING_TEXT", label: t("公安备案号"), value: POLICE_FILING_TEXT_ENV },
    { name: "VITE_POLICE_FILING_URL", label: t("公安备案链接"), value: POLICE_FILING_URL_ENV },
    { name: "VITE_POLICE_FILING_ICON", label: t("公安备案图标"), value: POLICE_FILING_ICON_ENV },
  ].filter((item) => item.value !== "");
  const filingEnvNames = filingEnvOverrides
    .map((item) => `${item.name}（${item.label}）`)
    .join("、");

  useEffect(() => {
    if (me && !isAdmin && tab === "site") {
      setTab("manage");
    }
  }, [me, isAdmin, tab]);

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
    if (tab === "tags") {
      tagsApi
        .list()
        .then(setTags)
        .catch(() => setError("加载标签失败"));
    }
    if (tab === "personal") {
      settingsApi
        .user()
        .then((settings) => {
          if (settings.link_mode) setLinkMode(settings.link_mode);
          if (settings.lang === "zh-CN" || settings.lang === "en-US") {
            setLang(settings.lang as Lang);
            document.documentElement.lang = settings.lang;
          }
          try {
            const feeds = JSON.parse(settings.rss_feeds ?? "[]") as unknown;
            if (Array.isArray(feeds)) {
              const urls = feeds.filter((u): u is string => typeof u === "string");
              setRssUrls([...urls, "", "", ""].slice(0, 3));
            }
          } catch {
            /* 忽略非法值 */
          }
        })
        .catch(() => undefined);
      backupApi
        .listSnapshots()
        .then(setSnapshots)
        .catch(() => setSnapshots([]));
      sessionsApi
        .list()
        .then(setSessions)
        .catch(() => setSessions([]));
    }
  }, [tab, setLang]);

  const saveSiteAction = useAsyncAction(
    async (patch: Parameters<typeof settingsApi.updateSite>[0]) => {
      const next = await settingsApi.updateSite(patch);
      setSite(next);
      toast.success(t("站点信息已保存"));
      if (filingEnvNames) {
        toast.warning(
          t("注意：备案信息由环境变量优先，本次修改的备案字段不会生效（{names}）", {
            names: filingEnvNames,
          }),
        );
      }
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
      toast.success(t("图片已上传，记得保存"));
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
      icon: newGroupIcon,
    });
    setNewGroupName("");
    setNewGroupPublic(false);
    setNewGroupIcon("folder");
    setGroups(await groupsApi.list());
    toast.success(t("分组已创建"));
  });

  const toggleGroupAction = useAsyncAction(
    async (group: GroupOut) => {
      await groupsApi.update(group.id, {
        name: group.name,
        icon: group.icon,
        is_public: !group.is_public,
      });
      setGroups(await groupsApi.list());
      toast.success(t("「{name}」已{status}", { name: group.name, status: group.is_public ? t("私密") : t("公开") }));
    },
    { onError: (err) => setError(err.message) },
  );

  const updateGroupIconAction = useAsyncAction(
    async ({ group, icon }: { group: GroupOut; icon: string | null }) => {
      await groupsApi.update(group.id, {
        name: group.name,
        icon,
        is_public: group.is_public,
      });
      setGroups(await groupsApi.list());
      toast.success(t("「{name}」图标已更新", { name: group.name }));
    },
    { onError: (err) => setError(err.message) },
  );

  const fetchIconAction = useAsyncAction(
    async (link: LinkOut) => {
      await linksApi.fetchIcon(link.id);
      setLinks(await linksApi.list());
      toast.success(t("「{name}」图标已抓取", { name: link.name }));
    },
    { onError: (err) => setError(err.message) },
  );

  const revokeSessionAction = useAsyncAction(async (id: number) => {
    await sessionsApi.revoke(id);
    setSessions(await sessionsApi.list());
    toast.success(t("会话已吊销"));
  }, { onError: (err) => setError(err.message) });

  const revokeAllSessionsAction = useAsyncAction(async () => {
    const result = await sessionsApi.revokeAll();
    setSessions(await sessionsApi.list());
    toast.success(t("已吊销 {n} 个其他会话", { n: result.revoked }));
  }, { onError: (err) => setError(err.message) });

  const unbindSsoAction = useAsyncAction(async () => {
    await ssoApi.unbind(unbindPassword);
    setUnbindOpen(false);
    setUnbindPassword("");
    setMe(await authApi.me());
    toast.success(t("SSO 已解绑"));
  }, { onError: (err) => setError(err.message) });

  const saveRssAction = useAsyncAction(async () => {
    const urls = rssUrls
      .map((url) => url.trim())
      .filter((url) => url !== "");
    await rssApi.setFeeds(urls);
    toast.success(urls.length > 0 ? t("订阅已保存") : t("订阅已清空"));
  }, { onError: (err) => setError(err.message) });

  const restoreSnapshotAction = useAsyncAction(async () => {
    if (restoreName === null) return;
    const result = await backupApi.restore(restoreName);
    const counts = result.restored;
    setRestoreName(null);
    setGroups(await groupsApi.list());
    setLinks(await linksApi.list());
    setSnapshots(await backupApi.listSnapshots());
    toast.success(
      `已恢复：分组 ${counts.groups}、链接 ${counts.links}、设置 ${counts.settings}、站点 ${counts.site_settings}`,
    );
  }, { onError: (err) => setError(err.message) });

  const exportBackupAction = useAsyncAction(async () => {
    const data = await backupApi.export();
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const date = new Date().toISOString().slice(0, 10).replaceAll("-", "");
    anchor.href = url;
    anchor.download = `lipanel-backup-${date}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success(t("备份已导出"));
  }, { onError: (err) => setError(err.message) });

  const importBackupAction = useAsyncAction(
    async (file: File) => {
      const text = await file.text();
      const data: unknown = JSON.parse(text);
      const result = await backupApi.import(data);
      const counts = result.imported;
      setGroups(await groupsApi.list());
      setLinks(await linksApi.list());
      toast.success(
        `导入完成：分组 ${counts.groups}、链接 ${counts.links}、设置 ${counts.settings}、站点 ${counts.site_settings}`,
      );
    },
    { onError: (err) => setError(err.message) },
  );

  const renameTagAction = useAsyncAction(
    async ({ oldName, newName }: { oldName: string; newName: string }) => {
      await tagsApi.rename(oldName, newName);
      setTags(await tagsApi.list());
      setEditingTag(null);
      setRenameValue("");
      setLinks(await linksApi.list().catch(() => links));
      toast.success(t("标签「{old}」已重命名为「{new}」", { old: oldName, new: newName }));
    },
    { onError: (err) => setError(err.message) },
  );

  const deleteTagAction = useAsyncAction(async () => {
    if (deleteTagName === null) return;
    await tagsApi.remove(deleteTagName);
    setTags(await tagsApi.list());
    setLinks(await linksApi.list().catch(() => links));
    setDeleteTagName(null);
    toast.success(t("标签「{name}」已删除", { name: deleteTagName }));
  }, { onError: (err) => setError(err.message) });

  const fetchMissingIconsAction = useAsyncAction(async () => {
    const missing = links.filter(
      (link) => link.icon_type === "letter" || !link.icon_value,
    );
    let ok = 0;
    for (const link of missing) {
      try {
        await linksApi.fetchIcon(link.id);
        ok += 1;
      } catch {
        /* 单个失败忽略，继续下一个 */
      }
    }
    setLinks(await linksApi.list());
    toast.success(
      t("已获取 {n}/{total} 个图标", { n: ok, total: missing.length }),
    );
  }, { onError: (err) => setError(err.message) });

  const batchDeleteAction = useAsyncAction(async () => {
    const count = selectedIds.size;
    await linksApi.batchDelete([...selectedIds]);
    setSelectedIds(new Set());
    setBatchDeleteOpen(false);
    setLinks(await linksApi.list());
    toast.success(t("已删除 {n} 个快捷方式", { n: count }));
  }, { onError: (err) => setError(err.message) });

  const batchMoveAction = useAsyncAction(async () => {
    const groupId = batchTargetGroup ? Number(batchTargetGroup) : null;
    await linksApi.batchMove([...selectedIds], groupId);
    setSelectedIds(new Set());
    setLinks(await linksApi.list());
    toast.success(t("已移动所选快捷方式"));
  }, { onError: (err) => setError(err.message) });

  const batchVisibilityAction = useAsyncAction(
    async (is_public: boolean) => {
      await linksApi.batchVisibility([...selectedIds], is_public);
      setSelectedIds(new Set());
      setLinks(await linksApi.list());
      toast.success(is_public ? t("已设为公开") : t("已设为私密"));
    },
    { onError: (err) => setError(err.message) },
  );

  const deleteGroupAction = useAsyncAction(
    async (id: number) => {
      await groupsApi.remove(id);
      setGroups(await groupsApi.list());
      toast.success(t("分组已删除，链接保留为未分组"));
      setDeleteGroupId(null);
    },
    { onError: (err) => setError(err.message) },
  );

  const saveLinkAction = useAsyncAction(async (force = false) => {
    const body = {
      name: linkForm.name,
      url_lan: linkForm.url_lan,
      url_wan: linkForm.url_wan || null,
      group_id: linkForm.group_id ? Number(linkForm.group_id) : null,
      description: linkForm.description,
      is_public: linkForm.is_public,
      guest_url_mode: linkForm.guest_url_mode,
      open_mode: linkForm.open_mode,
      tags: linkForm.tags,
      health_enabled: linkForm.health_enabled,
      health_interval: linkForm.health_interval,
      health_timeout: linkForm.health_timeout,
      health_threshold: linkForm.health_threshold,
      force,
    };
    if (linkForm.id === null) {
      await linksApi.create(body);
    } else {
      await linksApi.update(linkForm.id, body);
    }
    setLinkForm(emptyLinkForm);
    setDuplicateNotice(null);
    setLinks(await linksApi.list());
    toast.success(t("快捷方式已保存"));
    // 自动抓取图标为后台任务，稍后刷新以显示新图标
    window.setTimeout(() => {
      void linksApi.list().then(setLinks).catch(() => undefined);
    }, 8000);
  }, {
    onError: (err) => {
      const e = err as Error & { code?: string };
      if (e.code === "duplicate") {
        setDuplicateNotice(e.message);
      } else {
        setError(e.message);
      }
    },
  });

  const toggleLinkAction = useAsyncAction(
    async (link: LinkOut) => {
      await linksApi.update(link.id, {
        name: link.name,
        url_lan: link.url_lan,
        url_wan: link.url_wan,
        group_id: link.group_id,
        description: link.description,
        tags: link.tags,
        is_public: !link.is_public,
        guest_url_mode: link.guest_url_mode,
        open_mode: link.open_mode,
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

  function handleGroupDrop(target: GroupOut) {
    const sourceId = groupDragId;
    setGroupDragId(null);
    setGroupDragOverId(null);
    if (sourceId === null || sourceId === target.id) return;
    const ids = groups.map((group) => group.id);
    const from = ids.indexOf(sourceId);
    const to = ids.indexOf(target.id);
    if (from === -1 || to === -1) return;
    const next = [...ids];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    setGroups((current) => {
      const byId = new Map(current.map((group) => [group.id, group]));
      const ordered = next
        .map((id) => byId.get(id))
        .filter((group): group is GroupOut => Boolean(group));
      const rest = current.filter((group) => !next.includes(group.id));
      return [...ordered, ...rest];
    });
    groupsApi.updateOrder(next).catch(() => {
      toast.error("分组排序保存失败，已恢复原顺序");
      void groupsApi.list().then(setGroups).catch(() => undefined);
    });
  }

  if (!me) return <PageSkeleton title={t("管理")} />;

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background">
      <div className="relative z-10 flex flex-1 flex-col">
        <AppHeader
          title={t("管理")}
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
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 outline-none sm:px-6 lg:px-8"
        >
          <ScrollTabs fadeColor="var(--lipanel-bg)">
            {visibleTabs.map((item) => (
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
                {t(item.label)}
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
                    copyright: site.copyright,
                    icp: site.icp,
                    icp_url: site.icp_url,
                    icp_icon: site.icp_icon,
                    police_text: site.police_text,
                    police_url: site.police_url,
                    police_icon: site.police_icon,
                    public_mode: site.public_mode === "true",
                    notify_url: site.notify_url,
                    notify_enabled: site.notify_enabled,
                  });
                }}
                className="card space-y-4 p-6 sm:p-8"
              >
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block">
                    <span className="label">{t("站点名称")}</span>
                    <input
                      className="input"
                      value={site.site_name}
                      onChange={(e) =>
                        setSite({ ...site, site_name: e.target.value })
                      }
                    />
                  </label>
                  <label className="block">
                    <span className="label">{t("标语")}</span>
                    <input
                      className="input"
                      value={site.slogan}
                      onChange={(e) => setSite({ ...site, slogan: e.target.value })}
                    />
                  </label>
                </div>
                <label className="block">
                  <span className="label">{t("描述")}</span>
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
                    <span className="label">{t("Logo")}</span>
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
                    <span className="label">{t("favicon")}</span>
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
                {filingEnvNames ? (
                  <Notice intent="warning">
                    {t(
                      "备案信息优先读取构建期环境变量（{names}），后台修改不会生效；如需生效请清除对应 VITE_* 变量后重新构建。",
                      { names: filingEnvNames },
                    )}
                  </Notice>
                ) : null}
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
                    <span className="label">{t("版权行")}</span>
                    <input
                      className="input"
                      value={site.copyright}
                      onChange={(e) =>
                        setSite({ ...site, copyright: e.target.value })
                      }
                      placeholder={`© ${new Date().getFullYear()} ${site.site_name} · v${APP_VERSION}`}
                    />
                  </label>
                  <label className="block">
                    <span className="label">{t("备案号")}</span>
                    <input
                      className="input"
                      value={site.icp}
                      onChange={(e) => setSite({ ...site, icp: e.target.value })}
                    />
                  </label>
                  <label className="block">
                    <span className="label">{t("备案链接")}</span>
                    <input
                      className="input"
                      value={site.icp_url}
                      onChange={(e) => setSite({ ...site, icp_url: e.target.value })}
                      placeholder="https://beian.miit.gov.cn/"
                    />
                  </label>
                  <label className="block">
                    <span className="label">{t("备案图标")}</span>
                    <input
                      className="input"
                      value={site.icp_icon}
                      onChange={(e) => setSite({ ...site, icp_icon: e.target.value })}
                      placeholder="/badges/icp.webp"
                    />
                  </label>
                  <label className="block">
                    <span className="label">{t("公安备案号")}</span>
                    <input
                      className="input"
                      value={site.police_text}
                      onChange={(e) =>
                        setSite({ ...site, police_text: e.target.value })
                      }
                      placeholder="如：京公网安备 11000000000000 号"
                    />
                  </label>
                  <label className="block">
                    <span className="label">{t("公安备案链接")}</span>
                    <input
                      className="input"
                      value={site.police_url}
                      onChange={(e) => setSite({ ...site, police_url: e.target.value })}
                      placeholder="https://beian.mps.gov.cn/"
                    />
                  </label>
                  <label className="block">
                    <span className="label">{t("公安备案图标")}</span>
                    <input
                      className="input"
                      value={site.police_icon}
                      onChange={(e) =>
                        setSite({ ...site, police_icon: e.target.value })
                      }
                      placeholder="/badges/police.webp"
                    />
                  </label>
                </div>
                <div className="rounded-xl bg-surface-2/60 p-4">
                  <p className="text-sm font-medium text-foreground">{t("通知设置")}</p>
                  <p className="mt-1 text-xs text-muted">
                    链接状态变化时向 ntfy / Webhook 地址发送 JSON 通知。
                  </p>
                  <label className="mt-3 block">
                    <span className="label">{t("通知地址（ntfy / Webhook）")}</span>
                    <input
                      className="input"
                      value={site.notify_url}
                      onChange={(e) =>
                        setSite({ ...site, notify_url: e.target.value })
                      }
                      placeholder="https://ntfy.sh/your-topic 或 https://example.com/hook"
                    />
                  </label>
                  <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-primary"
                      checked={site.notify_enabled === "true"}
                      onChange={(e) =>
                        setSite({
                          ...site,
                          notify_enabled: e.target.checked ? "true" : "false",
                        })
                      }
                    />
                    {t("启用状态变化通知")}
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
                  {t("允许访客查看公开内容")}
                </label>
                <AsyncButton
                  type="submit"
                  status={saveSiteAction.status}
                  className="btn btn-primary"
                >
                  {t("保存站点信息")}
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
                    <span className="label">{t("新建分组")}</span>
                    <input
                      className="input"
                      value={newGroupName}
                      onChange={(e) => setNewGroupName(e.target.value)}
                      placeholder={t("分组名称")}
                      required
                    />
                  </div>
                  <div className="min-w-32">
                    <span className="label">图标</span>
                    <select
                      className="input"
                      value={newGroupIcon}
                      onChange={(e) =>
                        setNewGroupIcon(e.target.value as GroupIconName)
                      }
                    >
                      {GROUP_ICON_NAMES.map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <label className="flex cursor-pointer items-center gap-2 pb-2.5 text-sm text-foreground">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-primary"
                      checked={newGroupPublic}
                      onChange={(e) => setNewGroupPublic(e.target.checked)}
                    />
                    {t("公开")}
                  </label>
                  <AsyncButton
                    type="submit"
                    status={addGroupAction.status}
                    className="btn btn-primary"
                  >
                    {t("创建")}
                  </AsyncButton>
                </form>

                <div className="card p-6">
                  <h2 className="mb-3 text-sm font-semibold text-foreground">{t("分组")}</h2>
                  <div className="table-shell overflow-x-auto">
                    <table>
                      <thead>
                        <tr>
                          <th>{t("名称")}</th>
                          <th>{t("图标")}</th>
                          <th>{t("访客可见")}</th>
                          <th>{t("操作")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {groups.map((group) => (
                          <tr
                            key={group.id}
                            draggable
                            onDragStart={() => setGroupDragId(group.id)}
                            onDragOver={(event) => {
                              event.preventDefault();
                              if (groupDragId !== group.id) {
                                setGroupDragOverId(group.id);
                              }
                            }}
                            onDrop={(event) => {
                              event.preventDefault();
                              handleGroupDrop(group);
                            }}
                            onDragEnd={() => {
                              setGroupDragId(null);
                              setGroupDragOverId(null);
                            }}
                            className={`cursor-grab select-none active:cursor-grabbing ${
                              groupDragOverId === group.id
                                ? "bg-primary-soft"
                                : ""
                            }`}
                          >
                            <td className="min-w-36 font-medium">{group.name}</td>
                            <td className="min-w-32">
                              <select
                                className="input input-sm"
                                aria-label={`${group.name} 图标`}
                                value={isGroupIconName(group.icon) ? group.icon : ""}
                                onChange={(event) => {
                                  const value = event.target.value;
                                  void updateGroupIconAction.run({
                                    group,
                                    icon: value || null,
                                  });
                                }}
                              >
                                <option value="">默认</option>
                                {GROUP_ICON_NAMES.map((name) => (
                                  <option key={name} value={name}>
                                    {name}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td>
                              <span
                                className={`badge ${
                                  group.is_public ? "badge-primary" : "badge-muted"
                                }`}
                              >
                                {group.is_public ? t("公开") : t("私密")}
                              </span>
                            </td>
                            <td className="whitespace-nowrap">
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  aria-pressed={group.is_public}
                                  className="btn btn-ghost h-8 px-3 text-xs"
                                  onClick={() => void toggleGroupAction.run(group)}
                                >
                                  {t("切换可见性")}
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-danger h-8 px-3 text-xs"
                                  onClick={() => setDeleteGroupId(group.id)}
                                >
                                  {t("删除")}
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
                    {linkForm.id === null ? t("新建快捷方式") : t("编辑：{name}", { name: linkForm.name })}
                  </h2>
                  <input
                    className="input"
                    placeholder={t("名称")}
                    value={linkForm.name}
                    onChange={(e) => setLinkForm({ ...linkForm, name: e.target.value })}
                    required
                  />
                  <input
                    className="input"
                    placeholder={t("内网地址 http://…")}
                    value={linkForm.url_lan}
                    onChange={(e) =>
                      setLinkForm({ ...linkForm, url_lan: e.target.value })
                    }
                    required
                  />
                  <input
                    className="input"
                    placeholder={t("公网地址（可选）")}
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
                    <option value="">{t("未分组")}</option>
                    {groups.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                  <input
                    className="input sm:col-span-2"
                    placeholder={t("描述（可选）")}
                    value={linkForm.description}
                    onChange={(e) =>
                      setLinkForm({ ...linkForm, description: e.target.value })
                    }
                  />
                  <input
                    className="input sm:col-span-2"
                    placeholder={t("标签，用逗号分隔（最多 8 个）")}
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
                    {t("公开")}
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
                    <option value="hidden">{t("访客隐藏 URL（/go 跳转）")}</option>
                    <option value="show">{t("访客直接显示 URL")}</option>
                  </select>
                  <select
                    className="input"
                    value={linkForm.open_mode}
                    onChange={(e) =>
                      setLinkForm({
                        ...linkForm,
                        open_mode: e.target.value as "new_tab" | "modal",
                      })
                    }
                  >
                    <option value="new_tab">{t("新标签页打开")}</option>
                    <option value="modal">{t("内置窗口打开")}</option>
                  </select>
                  <div className="rounded-xl border border-border bg-surface-2/40 p-3 sm:col-span-2">
                    <p className="text-sm font-medium text-foreground">{t("健康检查")}</p>
                    <label className="mt-2 flex cursor-pointer items-center gap-2 text-sm text-foreground">
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-primary"
                        checked={linkForm.health_enabled}
                        onChange={(e) =>
                          setLinkForm({
                            ...linkForm,
                            health_enabled: e.target.checked,
                          })
                        }
                      />
                      {t("启用健康检查")}
                    </label>
                    <div className="mt-3 grid gap-3 sm:grid-cols-3">
                      <label className="block">
                        <span className="label">{t("间隔（分钟）")}</span>
                        <input
                          type="number"
                          min={1}
                          max={1440}
                          className="input"
                          value={linkForm.health_interval}
                          onChange={(e) =>
                            setLinkForm({
                              ...linkForm,
                              health_interval: Number(e.target.value) || 10,
                            })
                          }
                        />
                      </label>
                      <label className="block">
                        <span className="label">{t("超时（秒）")}</span>
                        <input
                          type="number"
                          min={0.5}
                          max={30}
                          step={0.5}
                          className="input"
                          value={linkForm.health_timeout}
                          onChange={(e) =>
                            setLinkForm({
                              ...linkForm,
                              health_timeout: Number(e.target.value) || 5,
                            })
                          }
                        />
                      </label>
                      <label className="block">
                        <span className="label">{t("连续失败阈值")}</span>
                        <input
                          type="number"
                          min={1}
                          max={10}
                          className="input"
                          value={linkForm.health_threshold}
                          onChange={(e) =>
                            setLinkForm({
                              ...linkForm,
                              health_threshold: Number(e.target.value) || 1,
                            })
                          }
                        />
                      </label>
                    </div>
                  </div>
                  {duplicateNotice ? (
                    <div className="sm:col-span-2">
                      <Notice intent="warning">{duplicateNotice}</Notice>
                      <button
                        type="button"
                        className="btn btn-ghost h-8 px-3 text-xs"
                        onClick={() => void saveLinkAction.run(true)}
                      >
                        仍要保存
                      </button>
                    </div>
                  ) : null}
                  <AsyncButton
                    type="submit"
                    status={saveLinkAction.status}
                    className="btn btn-primary sm:col-span-2"
                  >
                    {linkForm.id === null ? t("创建") : t("保存修改")}
                  </AsyncButton>
                </form>

                {selectedIds.size > 0 ? (
                  <div className="card flex flex-wrap items-center gap-3 p-4">
                    <span className="text-sm font-medium text-foreground">
                      {t("已选 {n} 项", { n: selectedIds.size })}
                    </span>
                    <select
                      className="input input-sm max-w-40"
                      value={batchTargetGroup}
                      onChange={(e) => setBatchTargetGroup(e.target.value)}
                      aria-label="移动到分组"
                    >
                      <option value="">{t("未分组")}</option>
                      {groups.map((group) => (
                        <option key={group.id} value={group.id}>
                          {group.name}
                        </option>
                      ))}
                    </select>
                    <AsyncButton
                      type="button"
                      status={batchMoveAction.status}
                      className="btn btn-ghost h-8 px-3 text-xs"
                      onClick={() => void batchMoveAction.run()}
                    >
                      {t("移动")}
                    </AsyncButton>
                    <button
                      type="button"
                      className="btn btn-ghost h-8 px-3 text-xs"
                      disabled={batchVisibilityAction.status === "pending"}
                      onClick={() => void batchVisibilityAction.run(true)}
                    >
                      {t("设为公开")}
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost h-8 px-3 text-xs"
                      disabled={batchVisibilityAction.status === "pending"}
                      onClick={() => void batchVisibilityAction.run(false)}
                    >
                      {t("设为私密")}
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger h-8 px-3 text-xs"
                      onClick={() => setBatchDeleteOpen(true)}
                    >
                      {t("删除")}
                    </button>
                  </div>
                ) : null}

                <div className="card p-6">
                  <div className="mb-3 flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-foreground">
                      {t("快捷方式")}（{links.length}）
                    </h2>
                    <button
                      type="button"
                      className="btn btn-ghost h-8 px-3 text-xs"
                      disabled={fetchMissingIconsAction.status === "pending"}
                      onClick={() => void fetchMissingIconsAction.run()}
                    >
                      {t("补抓缺失图标")}
                    </button>
                  </div>
                  <div className="table-shell overflow-x-auto">
                    <table>
                      <thead>
                        <tr>
                          <th className="w-10">
                            <input
                              type="checkbox"
                              aria-label="全选快捷方式"
                              className="h-4 w-4 accent-primary"
                              checked={
                                links.length > 0 &&
                                selectedIds.size === links.length
                              }
                              onChange={(e) =>
                                setSelectedIds(
                                  e.target.checked
                                    ? new Set(links.map((l) => l.id))
                                    : new Set(),
                                )
                              }
                            />
                          </th>
                          <th>{t("名称")}</th>
                          <th>{t("内网地址")}</th>
                          <th>{t("可见性")}</th>
                          <th>{t("操作")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {links.map((link) => (
                          <tr
                            key={link.id}
                            className={selectedIds.has(link.id) ? "bg-primary-soft/60" : ""}
                          >
                            <td>
                              <input
                                type="checkbox"
                                aria-label={`选择 ${link.name}`}
                                className="h-4 w-4 accent-primary"
                                checked={selectedIds.has(link.id)}
                                onChange={(e) =>
                                  setSelectedIds((current) => {
                                    const next = new Set(current);
                                    if (e.target.checked) {
                                      next.add(link.id);
                                    } else {
                                      next.delete(link.id);
                                    }
                                    return next;
                                  })
                                }
                              />
                            </td>
                            <td className="min-w-44 font-medium">{link.name}</td>
                            <td
                              className="table-cell-clip font-mono text-xs text-muted"
                              title={link.url_lan}
                            >
                              {link.url_lan}
                            </td>
                            <td>
                              <span
                                className={`badge ${
                                  link.is_public ? "badge-primary" : "badge-muted"
                                }`}
                              >
                                {link.is_public ? t("公开") : t("私密")}
                              </span>
                            </td>
                            <td className="whitespace-nowrap">
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  className="btn btn-ghost h-8 px-3 text-xs"
                                  disabled={fetchIconAction.status === "pending"}
                                  onClick={() => void fetchIconAction.run(link)}
                                >
                                  {t("抓图标")}
                                </button>
                                <button
                                  type="button"
                                  aria-pressed={link.is_public}
                                  className="btn btn-ghost h-8 px-3 text-xs"
                                  onClick={() => void toggleLinkAction.run(link)}
                                >
                                  {t("切换")}
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-ghost h-8 px-3 text-xs"
                                  onClick={() => {
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
                                      open_mode: link.open_mode,
                                      tags: link.tags,
                                      health_enabled: link.health_enabled,
                                      health_interval: link.health_interval,
                                      health_timeout: link.health_timeout,
                                      health_threshold: link.health_threshold,
                                    });
                                    setDuplicateNotice(null);
                                  }}
                                >
                                  {t("编辑")}
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-danger h-8 px-3 text-xs"
                                  onClick={() => setDeleteLinkId(link.id)}
                                >
                                  {t("删除")}
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

            {tab === "tags" ? (
              <div className="card p-6">
                <h2 className="mb-3 text-sm font-semibold text-foreground">
                  {t("标签（{n}）", { n: tags.length })}
                </h2>
                {tags.length === 0 ? (
                  <p className="text-sm text-muted">
                    {t("还没有标签，给快捷方式添加标签后会显示在这里。")}
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {tags.map((tag) => (
                      <li
                        key={tag.name}
                        className="flex flex-wrap items-center gap-2 py-2.5"
                      >
                        {editingTag === tag.name ? (
                          <>
                            <input
                              className="input input-sm max-w-48"
                              value={renameValue}
                              onChange={(e) => setRenameValue(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                  void renameTagAction.run({
                                    oldName: tag.name,
                                    newName: renameValue,
                                  });
                                }
                                if (e.key === "Escape") {
                                  setEditingTag(null);
                                }
                              }}
                              aria-label="新标签名"
                              autoFocus
                            />
                            <button
                              type="button"
                              className="btn btn-primary h-8 px-3 text-xs"
                              disabled={renameTagAction.status === "pending"}
                              onClick={() =>
                                void renameTagAction.run({
                                  oldName: tag.name,
                                  newName: renameValue,
                                })
                              }
                            >
                              {t("保存")}
                            </button>
                            <button
                              type="button"
                              className="btn btn-ghost h-8 px-3 text-xs"
                              onClick={() => setEditingTag(null)}
                            >
                              {t("取消")}
                            </button>
                          </>
                        ) : (
                          <>
                            <span className="badge badge-muted">{tag.name}</span>
                            <span className="text-xs text-muted">
                              {t("{n} 个快捷方式", { n: tag.count })}
                            </span>
                            <div className="ml-auto flex gap-2">
                              <button
                                type="button"
                                className="btn btn-ghost h-8 px-3 text-xs"
                                onClick={() => {
                                  setEditingTag(tag.name);
                                  setRenameValue(tag.name);
                                }}
                              >
                                {t("重命名")}
                              </button>
                              <button
                                type="button"
                                className="btn btn-danger h-8 px-3 text-xs"
                                onClick={() => setDeleteTagName(tag.name)}
                              >
                                {t("删除")}
                              </button>
                            </div>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : null}

            {tab === "personal" ? (
              <div className="card space-y-5 p-6 sm:p-8">
                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <span className="label">{t("语言")}</span>
                  <select
                    className="input"
                    value={lang}
                    onChange={(e) => handleLangChange(e.target.value as Lang)}
                    aria-label={t("语言")}
                  >
                    <option value="zh-CN">中文</option>
                    <option value="en-US">English</option>
                  </select>
                </div>
                <div>
                  <span className="label">{t("主题")}</span>
                  <select
                    className="input"
                    value={theme}
                    onChange={(e) => {
                      const next = e.target.value as "light" | "dark";
                      setTheme(next);
                      void saveUserAction.run({ theme: next });
                    }}
                  >
                    <option value="light">{t("浅色")}</option>
                    <option value="dark">{t("深色")}</option>
                  </select>
                  </div>
                <div>
                  <span className="label">{t("链接模式")}</span>
                  <select
                    className="input"
                    value={linkMode}
                    onChange={(e) => {
                      setLinkMode(e.target.value);
                      void saveUserAction.run({ link_mode: e.target.value });
                    }}
                  >
                    <option value="lan">{t("内网优先")}</option>
                    <option value="wan">{t("公网优先")}</option>
                  </select>
                  </div>
                </div>
                <div className="rounded-xl bg-surface-2/60 p-4">
                  <p className="text-sm font-medium text-foreground">{t("SSO 绑定")}</p>
                  {me.sso.bound ? (
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <p className="text-sm text-muted">
                        {t("已绑定：{provider}（{email}）", { provider: me.sso.provider ?? "", email: me.sso.email ?? "" })}
                      </p>
                      <button
                        type="button"
                        className="btn btn-danger ml-auto h-8 px-3 text-xs"
                        onClick={() => setUnbindOpen(true)}
                      >
                        {t("解绑")}
                      </button>
                    </div>
                  ) : (
                    <p className="mt-1 text-sm text-muted">{t("未绑定")}</p>
                  )}
                </div>
                <div className="rounded-xl border border-border p-4">
                  <p className="text-sm font-medium text-foreground">{t("会话管理")}</p>
                  <p className="mt-1 text-xs text-muted">
                    {t("查看并吊销其他设备上的登录会话。")}
                  </p>
                  {sessions.length > 0 ? (
                    <ul className="mt-3 max-h-40 divide-y divide-border overflow-y-auto rounded-lg border border-border">
                      {sessions.map((session) => (
                        <li
                          key={session.id}
                          className="flex items-center gap-2 px-3 py-2 text-xs"
                        >
                          <span className="min-w-0 truncate text-muted">
                            {t("最近使用 {time}", { time: session.last_used_at ?? session.created_at })}
                          </span>
                          {session.current ? (
                            <span className="badge badge-primary shrink-0">
                              {t("当前")}
                            </span>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-danger ml-auto h-8 shrink-0 px-2 text-xs"
                              disabled={revokeSessionAction.status === "pending"}
                              onClick={() => void revokeSessionAction.run(session.id)}
                            >
                              {t("吊销")}
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {sessions.some((session) => !session.current) ? (
                    <AsyncButton
                      type="button"
                      status={revokeAllSessionsAction.status}
                      className="btn btn-ghost mt-3 h-8 px-3 text-xs"
                      onClick={() => void revokeAllSessionsAction.run()}
                    >
                      {t("吊销其他会话")}
                    </AsyncButton>
                  ) : null}
                </div>
                <div className="rounded-xl border border-border p-4">
                  <p className="text-sm font-medium text-foreground">{t("RSS 订阅")}</p>
                  <p className="mt-1 text-xs text-muted">
                    {t("最多 3 个订阅源，面板展示最近条目（服务端解析缓存，超时 8s）。")}
                  </p>
                  <div className="mt-3 space-y-2">
                    {rssUrls.map((url, index) => (
                      <input
                        key={index}
                        className="input"
                        placeholder={t("订阅源 {n}（可选）", { n: index + 1 })}
                        value={url}
                        onChange={(e) =>
                          setRssUrls((current) =>
                            current.map((value, i) =>
                              i === index ? e.target.value : value,
                            ),
                          )
                        }
                      />
                    ))}
                  </div>
                  <AsyncButton
                    type="button"
                    status={saveRssAction.status}
                    className="btn btn-ghost mt-3 h-8 px-3 text-xs"
                    onClick={() => void saveRssAction.run()}
                  >
                    {t("保存订阅")}
                  </AsyncButton>
                </div>
                <div className="rounded-xl border border-border p-4">
                  <p className="text-sm font-medium text-foreground">{t("数据备份")}</p>
                  <p className="mt-1 text-xs text-muted">
                    {t("导出分组、快捷方式与个人设置；导入为追加合并，不会删除现有数据。")}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <AsyncButton
                      type="button"
                      status={exportBackupAction.status}
                      className="btn btn-ghost h-8 px-3 text-xs"
                      onClick={() => void exportBackupAction.run()}
                    >
                      {t("导出备份")}
                    </AsyncButton>
                    <label className="btn btn-ghost h-8 cursor-pointer px-3 text-xs">
                      {importBackupAction.status === "pending"
                        ? t("导入中…")
                        : t("导入备份")}
                      <input
                        type="file"
                        accept="application/json,.json"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) void importBackupAction.run(file);
                          e.target.value = "";
                        }}
                      />
                    </label>
                  </div>
                  {snapshots.length > 0 ? (
                    <div className="mt-4">
                      <p className="text-xs font-medium text-muted">{t("自动快照")}</p>
                      <ul className="mt-2 max-h-48 divide-y divide-border overflow-y-auto rounded-lg border border-border">
                        {snapshots.map((snap) => (
                          <li
                            key={snap.name}
                            className="flex items-center gap-2 px-3 py-2 text-xs"
                          >
                            <span className="min-w-0 truncate font-mono text-muted">
                              {snap.created_at ?? snap.name}
                            </span>
                            <span className="shrink-0 text-muted">
                              {snap.groups} {t("组")} / {snap.links} {t("链接")}
                            </span>
                            <button
                              type="button"
                              className="btn btn-ghost ml-auto h-8 shrink-0 px-2 text-xs"
                              onClick={() => setRestoreName(snap.name)}
                            >
                              {t("恢复")}
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        </main>
        <SiteFooter site={site} />
      </div>

      <ConfirmDialog
        open={deleteGroupId !== null}
        title={t("删除分组")}
        message={t("删除后该分组下的快捷方式将保留为「未分组」。")}
        confirmLabel={t("删除")}
        status={deleteGroupAction.status}
        onConfirm={() => {
          if (deleteGroupId !== null) void deleteGroupAction.run(deleteGroupId);
        }}
        onCancel={() => setDeleteGroupId(null)}
      />
      <ConfirmDialog
        open={unbindOpen}
        title={t("解绑 SSO")}
        message={t("解绑后仍可用本地账号密码登录，确定继续？")}
        confirmLabel={t("解绑")}
        status={unbindSsoAction.status}
        onConfirm={() => void unbindSsoAction.run()}
        onCancel={() => {
          setUnbindOpen(false);
          setUnbindPassword("");
        }}
      >
        <div className="mt-3">
          <span className="label">{t("本地密码")}</span>
          <PasswordInput
            value={unbindPassword}
            onChange={(e) => setUnbindPassword(e.target.value)}
            className="input"
            autoComplete="current-password"
            placeholder={t("本地密码")}
          />
        </div>
      </ConfirmDialog>
      <ConfirmDialog
        open={restoreName !== null}
        title={t("从快照恢复")}
        message={t("恢复为追加导入（不会删除现有数据），确定继续？")}
        confirmLabel={t("恢复")}
        status={restoreSnapshotAction.status}
        onConfirm={() => void restoreSnapshotAction.run()}
        onCancel={() => setRestoreName(null)}
      />
      <ConfirmDialog
        open={deleteTagName !== null}
        title={t("删除标签")}
        message={t("确定删除标签「{name}」？会从所有快捷方式中移除该标签。", { name: deleteTagName ?? "" })}
        confirmLabel="删除"
        status={deleteTagAction.status}
        onConfirm={() => void deleteTagAction.run()}
        onCancel={() => setDeleteTagName(null)}
      />
      <ConfirmDialog
        open={batchDeleteOpen}
        title={t("批量删除")}
        message={t("确定删除选中的 {n} 个快捷方式？删除后不可恢复。", { n: selectedIds.size })}
        confirmLabel="删除"
        status={batchDeleteAction.status}
        onConfirm={() => void batchDeleteAction.run()}
        onCancel={() => setBatchDeleteOpen(false)}
      />
      <ConfirmDialog
        open={deleteLinkId !== null}
        title={t("删除快捷方式")}
        message={t("删除后不可恢复。")}
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
