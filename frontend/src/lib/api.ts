export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface SiteInfo {
  site_name: string;
  slogan: string;
  description: string;
  logo: string;
  favicon: string;
  footer_text: string;
  icp: string;
  public_mode: string;
  oidc_enabled?: boolean;
}

export interface LinkItem {
  id: number;
  group_id?: number | null;
  name: string;
  url?: string;
  url_lan?: string;
  url_wan?: string | null;
  icon_type: "letter" | "iconify" | "upload";
  icon_value?: string | null;
  description: string;
  tags: string[];
  is_public?: boolean;
  guest_url_mode?: "hidden" | "show";
  open_mode: "new_tab" | "modal";
}

export interface Group {
  id: number;
  name: string;
  icon?: string | null;
  is_public?: boolean;
  links: LinkItem[];
}

export interface GroupRow {
  id: number;
  name: string;
  icon: string | null;
  is_public: boolean;
  sort_order: number;
}

export interface PanelData {
  site: SiteInfo;
  groups: Group[];
  ungrouped: LinkItem[];
}

export interface Me {
  user: { id: number; username: string; role: string };
  sso: { bound: boolean; provider: string | null; email: string | null };
}

export type SiteSettingsPatch = Partial<
  Omit<SiteInfo, "oidc_enabled" | "public_mode">
> & { public_mode?: boolean };

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...options, headers, credentials: "same-origin" });
  if (res.status === 204) {
    return undefined as T;
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail;
    const message = Array.isArray(detail)
      ? "输入不合法"
      : typeof detail === "string"
        ? detail
        : "请求失败";
    throw new ApiError(res.status, message);
  }
  return data as T;
}

export const api = {
  getPanel: () => request<PanelData>("/api/panel"),
  me: () => request<Me>("/api/auth/me"),
  login: (username: string, password: string) =>
    request<{ user: Me["user"] }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  setupStatus: () => request<{ required: boolean }>("/api/setup-status"),
  createAdmin: (username: string, password: string) =>
    request<{ id: number }>("/api/setup", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  ssoLinkStatus: () =>
    request<{ valid: boolean; email?: string | null; nickname?: string | null }>(
      "/api/sso/link-status",
    ),
  ssoLink: (action: "bind" | "create", username: string, password: string) =>
    request<{ ok: boolean }>("/api/sso/link", {
      method: "POST",
      body: JSON.stringify({ action, username, password }),
    }),
  siteSettings: () => request<SiteInfo>("/api/site-settings"),
  updateSiteSettings: (patch: SiteSettingsPatch) =>
    request<SiteInfo>("/api/site-settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ url: string }>("/api/uploads", {
      method: "POST",
      body: form,
    });
  },
  userSettings: () => request<Record<string, string>>("/api/settings"),
  updateUserSettings: (patch: Record<string, string>) =>
    request<Record<string, string>>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  listGroups: () => request<GroupRow[]>("/api/groups"),
  createGroup: (body: { name: string; is_public: boolean }) =>
    request<Group>("/api/groups", { method: "POST", body: JSON.stringify(body) }),
  updateGroup: (id: number, body: { name: string; is_public: boolean }) =>
    request<Group>(`/api/groups/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteGroup: (id: number) =>
    request<void>(`/api/groups/${id}`, { method: "DELETE" }),
  listLinks: () => request<LinkItem[]>("/api/links"),
  createLink: (body: Partial<LinkItem> & { name: string; url_lan: string }) =>
    request<LinkItem>("/api/links", { method: "POST", body: JSON.stringify(body) }),
  updateLink: (id: number, body: Partial<LinkItem> & { name: string; url_lan: string }) =>
    request<LinkItem>(`/api/links/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteLink: (id: number) => request<void>(`/api/links/${id}`, { method: "DELETE" }),
};
