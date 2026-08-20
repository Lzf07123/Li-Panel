export interface UserOut {
  id: number;
  username: string;
  role: string;
}

export interface MeOut {
  user: UserOut;
  sso: {
    bound: boolean;
    provider: string | null;
    email: string | null;
  };
}

export interface SiteSettings {
  site_name: string;
  slogan: string;
  description: string;
  logo: string;
  favicon: string;
  footer_text: string;
  copyright: string;
  icp: string;
  icp_url: string;
  icp_icon: string;
  police_text: string;
  police_url: string;
  police_icon: string;
  public_mode: string;
  notify_url: string;
  notify_enabled: string;
  oidc_enabled?: boolean;
}

export type LinkOut = {
  id: number;
  group_id: number | null;
  name: string;
  url_lan: string;
  url_wan: string | null;
  url?: string;
  icon_type: "letter" | "iconify" | "upload";
  icon_value: string | null;
  description: string;
  tags: string[];
  is_public: boolean;
  guest_url_mode: "hidden" | "show";
  sort_order: number;
  open_mode: "new_tab" | "modal";
  health_enabled: boolean;
  health_interval: number;
  health_timeout: number;
  health_threshold: number;
};

export interface GroupOut {
  id: number;
  name: string;
  icon: string | null;
  is_public: boolean;
  sort_order: number;
  links: LinkOut[];
}

export interface PanelOut {
  site: SiteSettings;
  groups: GroupOut[];
  ungrouped: LinkOut[];
}
