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
  icp: string;
  public_mode: string;
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
