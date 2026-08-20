import type {
  GroupOut,
  LinkOut,
  MeOut,
  PanelOut,
  SiteSettings,
  UserOut,
} from "./types";

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "";
export const API_BASE_URL = BASE_URL;

interface ApiOptions {
  /** 静默会话探针：401 视为预期结果，不派发全局 unauthorized 跳转事件 */
  silent401?: boolean;
}

async function api<T>(
  path: string,
  init: RequestInit = {},
  options: ApiOptions = {},
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(init.headers ?? {}),
    },
  });
  if (
    response.status === 401 &&
    isSessionGuardedPath(path) &&
    !options.silent401
  ) {
    window.dispatchEvent(new Event("lipass:unauthorized"));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: unknown;
    };
    if (typeof body.detail === "string") {
      throw new Error(body.detail);
    }
    if (Array.isArray(body.detail)) {
      throw new Error(
        body.detail
          .map((item) =>
            item && typeof item === "object"
              ? String((item as { msg?: unknown }).msg ?? "")
              : String(item),
          )
          .filter(Boolean)
          .join("；"),
      );
    }
    throw new Error(`请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

function isSessionGuardedPath(path: string): boolean {
  return (
    !path.startsWith("/api/auth/") &&
    !path.startsWith("/api/setup") &&
    !path.startsWith("/api/sso/")
  );
}

export const authApi = {
  login: (data: { username: string; password: string }) =>
    api<{ user: UserOut }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  logout: () => api<{ message: string }>("/api/auth/logout", { method: "POST" }),
  me: () => api<MeOut>("/api/auth/me"),
  meSilent: () => api<MeOut>("/api/auth/me", {}, { silent401: true }),
  setupStatus: () => api<{ required: boolean }>("/api/setup-status"),
  createAdmin: (data: { username: string; password: string }) =>
    api<{ id: number }>("/api/setup", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  ssoLinkStatus: () =>
    api<{ valid: boolean; email?: string | null; nickname?: string | null }>(
      "/api/sso/link-status",
    ),
  ssoLink: (data: {
    action: "bind" | "create";
    username: string;
    password: string;
  }) =>
    api<{ ok: boolean }>("/api/sso/link", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export const panelApi = {
  get: () => api<PanelOut>("/api/panel"),
};

export const groupsApi = {
  list: () => api<GroupOut[]>("/api/groups"),
  create: (data: {
    name: string;
    is_public: boolean;
    icon?: string | null;
  }) => api<GroupOut>("/api/groups", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: {
    name: string;
    is_public: boolean;
    icon?: string | null;
  }) =>
    api<GroupOut>(`/api/groups/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  remove: (id: number) =>
    api<void>(`/api/groups/${id}`, { method: "DELETE" }),
  updateOrder: (ordered_ids: number[]) =>
    api<{ ok: boolean }>("/api/groups/order", {
      method: "PATCH",
      body: JSON.stringify({ ordered_ids }),
    }),
};

export const linksApi = {
  list: () => api<LinkOut[]>("/api/links"),
  create: (data: Partial<LinkOut> & { name: string; url_lan: string }) =>
    api<LinkOut>("/api/links", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Partial<LinkOut> & { name: string; url_lan: string }) =>
    api<LinkOut>(`/api/links/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  remove: (id: number) => api<void>(`/api/links/${id}`, { method: "DELETE" }),
  updateOrder: (ordered_ids: number[]) =>
    api<{ ok: boolean }>("/api/links/order", {
      method: "PATCH",
      body: JSON.stringify({ ordered_ids }),
    }),
  fetchIcon: (id: number) =>
    api<LinkOut>(`/api/links/${id}/fetch-icon`, { method: "POST" }),
  batchDelete: (ids: number[]) =>
    api<{ deleted: number }>("/api/links/batch-delete", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  batchMove: (ids: number[], group_id: number | null) =>
    api<{ moved: number }>("/api/links/batch-move", {
      method: "POST",
      body: JSON.stringify({ ids, group_id }),
    }),
  batchVisibility: (ids: number[], is_public: boolean) =>
    api<{ updated: number }>("/api/links/batch-visibility", {
      method: "POST",
      body: JSON.stringify({ ids, is_public }),
    }),
};

export const tagsApi = {
  list: () => api<{ name: string; count: number }[]>("/api/tags"),
  rename: (tag: string, name: string) =>
    api<{ renamed: number }>(`/api/tags/${encodeURIComponent(tag)}`, {
      method: "PUT",
      body: JSON.stringify({ name }),
    }),
  remove: (tag: string) =>
    api<{ removed: number }>(`/api/tags/${encodeURIComponent(tag)}`, {
      method: "DELETE",
    }),
};

export const settingsApi = {
  site: () => api<SiteSettings>("/api/site-settings"),
  updateSite: (
    patch: Partial<
      Omit<SiteSettings, "oidc_enabled" | "public_mode">
    > & { public_mode?: boolean },
  ) =>
    api<SiteSettings>("/api/site-settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  user: () => api<Record<string, string>>("/api/settings"),
  updateUser: (patch: Record<string, string>) =>
    api<Record<string, string>>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<{ url: string }>("/api/uploads", {
      method: "POST",
      body: form,
    });
  },
};
