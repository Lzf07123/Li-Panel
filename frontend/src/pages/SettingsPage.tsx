import { useEffect, useState } from "react";

import { authApi, backupApi, groupsApi, linksApi, rssApi, settingsApi, tagsApi } from "../api/client";
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
import { GROUP_ICON_NAMES, GroupIcon, isGroupIconName } from "../components/GroupIcon";
import type { GroupIconName } from "../components/GroupIcon";
import { formatTags, parseTags } from "../lib/tags";

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
      icon: newGroupIcon,
    });
    setNewGroupName("");
    setNewGroupPublic(false);
    setNewGroupIcon("folder");
    setGroups(await groupsApi.list());
    toast.success("分组已创建");
  });

  const toggleGroupAction = useAsyncAction(
    async (group: GroupOut) => {
      await groupsApi.update(group.id, {
        name: group.name,
        icon: group.icon,
        is_public: !group.is_public,
      });
      setGroups(await groupsApi.list());
      toast.success(`「${group.name}」已${group.is_public ? "私密" : "公开"}`);
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
      toast.success(`「${group.name}」图标已更新`);
    },
    { onError: (err) => setError(err.message) },
  );

  const fetchIconAction = useAsyncAction(
    async (link: LinkOut) => {
      await linksApi.fetchIcon(link.id);
      setLinks(await linksApi.list());
      toast.success(`「${link.name}」图标已抓取`);
    },
    { onError: (err) => setError(err.message) },
  );

  const saveRssAction = useAsyncAction(async () => {
    const urls = rssUrls
      .map((url) => url.trim())
      .filter((url) => url !== "");
    await rssApi.setFeeds(urls);
    toast.success(urls.length > 0 ? "订阅已保存" : "订阅已清空");
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
    toast.success("备份已导出");
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
      toast.success(`标签「${oldName}」已重命名为「${newName}」`);
    },
    { onError: (err) => setError(err.message) },
  );

  const deleteTagAction = useAsyncAction(async () => {
    if (deleteTagName === null) return;
    await tagsApi.remove(deleteTagName);
    setTags(await tagsApi.list());
    setLinks(await linksApi.list().catch(() => links));
    setDeleteTagName(null);
    toast.success(`标签「${deleteTagName}」已删除`);
  }, { onError: (err) => setError(err.message) });

  const batchDeleteAction = useAsyncAction(async () => {
    const count = selectedIds.size;
    await linksApi.batchDelete([...selectedIds]);
    setSelectedIds(new Set());
    setBatchDeleteOpen(false);
    setLinks(await linksApi.list());
    toast.success(`已删除 ${count} 个快捷方式`);
  }, { onError: (err) => setError(err.message) });

  const batchMoveAction = useAsyncAction(async () => {
    const groupId = batchTargetGroup ? Number(batchTargetGroup) : null;
    await linksApi.batchMove([...selectedIds], groupId);
    setSelectedIds(new Set());
    setLinks(await linksApi.list());
    toast.success("已移动所选快捷方式");
  }, { onError: (err) => setError(err.message) });

  const batchVisibilityAction = useAsyncAction(
    async (is_public: boolean) => {
      await linksApi.batchVisibility([...selectedIds], is_public);
      setSelectedIds(new Set());
      setLinks(await linksApi.list());
      toast.success(is_public ? "已设为公开" : "已设为私密");
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
    toast.success("快捷方式已保存");
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
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 outline-none sm:px-6 lg:px-8"
        >
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
                          <th>图标</th>
                          <th>访客可见</th>
                          <th>操作</th>
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
                                {group.is_public ? "公开" : "私密"}
                              </span>
                            </td>
                            <td className="whitespace-nowrap">
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
                    <option value="new_tab">新标签页打开</option>
                    <option value="modal">内置窗口打开</option>
                  </select>
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
                    {linkForm.id === null ? "创建" : "保存修改"}
                  </AsyncButton>
                </form>

                {selectedIds.size > 0 ? (
                  <div className="card flex flex-wrap items-center gap-3 p-4">
                    <span className="text-sm font-medium text-foreground">
                      已选 {selectedIds.size} 项
                    </span>
                    <select
                      className="input input-sm max-w-40"
                      value={batchTargetGroup}
                      onChange={(e) => setBatchTargetGroup(e.target.value)}
                      aria-label="移动到分组"
                    >
                      <option value="">未分组</option>
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
                      移动
                    </AsyncButton>
                    <button
                      type="button"
                      className="btn btn-ghost h-8 px-3 text-xs"
                      disabled={batchVisibilityAction.status === "pending"}
                      onClick={() => void batchVisibilityAction.run(true)}
                    >
                      设为公开
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost h-8 px-3 text-xs"
                      disabled={batchVisibilityAction.status === "pending"}
                      onClick={() => void batchVisibilityAction.run(false)}
                    >
                      设为私密
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger h-8 px-3 text-xs"
                      onClick={() => setBatchDeleteOpen(true)}
                    >
                      删除
                    </button>
                  </div>
                ) : null}

                <div className="card p-6">
                  <h2 className="mb-3 text-sm font-semibold text-foreground">
                    快捷方式（{links.length}）
                  </h2>
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
                          <th>名称</th>
                          <th>内网地址</th>
                          <th>可见性</th>
                          <th>操作</th>
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
                            <td className="whitespace-nowrap">
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  className="btn btn-ghost h-8 px-3 text-xs"
                                  disabled={fetchIconAction.status === "pending"}
                                  onClick={() => void fetchIconAction.run(link)}
                                >
                                  抓图标
                                </button>
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
                                    });
                                    setDuplicateNotice(null);
                                  }}
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

            {tab === "tags" ? (
              <div className="card p-6">
                <h2 className="mb-3 text-sm font-semibold text-foreground">
                  标签（{tags.length}）
                </h2>
                {tags.length === 0 ? (
                  <p className="text-sm text-muted">
                    还没有标签，给快捷方式添加标签后会显示在这里。
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
                              保存
                            </button>
                            <button
                              type="button"
                              className="btn btn-ghost h-8 px-3 text-xs"
                              onClick={() => setEditingTag(null)}
                            >
                              取消
                            </button>
                          </>
                        ) : (
                          <>
                            <span className="badge badge-muted">{tag.name}</span>
                            <span className="text-xs text-muted">
                              {tag.count} 个快捷方式
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
                                重命名
                              </button>
                              <button
                                type="button"
                                className="btn btn-danger h-8 px-3 text-xs"
                                onClick={() => setDeleteTagName(tag.name)}
                              >
                                删除
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
                <div className="rounded-xl border border-border p-4">
                  <p className="text-sm font-medium text-foreground">RSS 订阅</p>
                  <p className="mt-1 text-xs text-muted">
                    最多 3 个订阅源，面板展示最近条目（服务端解析缓存，超时 8s）。
                  </p>
                  <div className="mt-3 space-y-2">
                    {rssUrls.map((url, index) => (
                      <input
                        key={index}
                        className="input input-sm"
                        placeholder={`订阅源 ${index + 1}（可选）`}
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
                    保存订阅
                  </AsyncButton>
                </div>
                <div className="rounded-xl border border-border p-4">
                  <p className="text-sm font-medium text-foreground">数据备份</p>
                  <p className="mt-1 text-xs text-muted">
                    导出分组、快捷方式与个人设置；导入为追加合并，不会删除现有数据。
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <AsyncButton
                      type="button"
                      status={exportBackupAction.status}
                      className="btn btn-ghost h-8 px-3 text-xs"
                      onClick={() => void exportBackupAction.run()}
                    >
                      导出备份
                    </AsyncButton>
                    <label className="btn btn-ghost h-8 cursor-pointer px-3 text-xs">
                      {importBackupAction.status === "pending"
                        ? "导入中…"
                        : "导入备份"}
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
                      <p className="text-xs font-medium text-muted">自动快照</p>
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
                              {snap.groups} 组 / {snap.links} 链接
                            </span>
                            <button
                              type="button"
                              className="btn btn-ghost ml-auto h-7 shrink-0 px-2 text-xs"
                              onClick={() => setRestoreName(snap.name)}
                            >
                              恢复
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
        open={restoreName !== null}
        title="从快照恢复"
        message="恢复为追加导入（不会删除现有数据），确定继续？"
        confirmLabel="恢复"
        status={restoreSnapshotAction.status}
        onConfirm={() => void restoreSnapshotAction.run()}
        onCancel={() => setRestoreName(null)}
      />
      <ConfirmDialog
        open={deleteTagName !== null}
        title="删除标签"
        message={`确定删除标签「${deleteTagName ?? ""}」？会从所有快捷方式中移除该标签。`}
        confirmLabel="删除"
        status={deleteTagAction.status}
        onConfirm={() => void deleteTagAction.run()}
        onCancel={() => setDeleteTagName(null)}
      />
      <ConfirmDialog
        open={batchDeleteOpen}
        title="批量删除"
        message={`确定删除选中的 ${selectedIds.size} 个快捷方式？删除后不可恢复。`}
        confirmLabel="删除"
        status={batchDeleteAction.status}
        onConfirm={() => void batchDeleteAction.run()}
        onCancel={() => setBatchDeleteOpen(false)}
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
