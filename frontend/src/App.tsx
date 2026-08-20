import { lazy, Suspense, useEffect, useRef } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AuthSkeleton } from "./components/AuthSkeleton";
import { GuestOnly } from "./components/GuestOnly";
import { PageSkeleton } from "./components/PageSkeleton";

const LoginPage = lazy(() =>
  import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })),
);
const SetupPage = lazy(() =>
  import("./pages/SetupPage").then((m) => ({ default: m.SetupPage })),
);
const SsoLinkPage = lazy(() =>
  import("./pages/SsoLinkPage").then((m) => ({ default: m.SsoLinkPage })),
);
const PanelPage = lazy(() =>
  import("./pages/PanelPage").then((m) => ({ default: m.PanelPage })),
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })),
);

const AUTH_ROUTES = new Set(["/login", "/setup", "/sso/link"]);

function PageFallback() {
  const { pathname } = useLocation();
  if (AUTH_ROUTES.has(pathname)) {
    return <AuthSkeleton />;
  }
  return <PageSkeleton />;
}

export function AppRoutes() {
  const location = useLocation();
  const firstRender = useRef(true);

  useEffect(() => {
    firstRender.current = false;
  }, []);

  return (
    <div
      key={location.pathname}
      className={firstRender.current ? "min-h-screen" : "page-enter min-h-screen"}
    >
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/login" element={<GuestOnly><LoginPage /></GuestOnly>} />
          <Route path="/setup" element={<GuestOnly><SetupPage /></GuestOnly>} />
          <Route path="/sso/link" element={<SsoLinkPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/" element={<PanelPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </div>
  );
}

export default function App() {
  useEffect(() => {
    const onUnauthorized = () => {
      const { pathname, search } = window.location;
      if (pathname === "/login") return;
      const next = encodeURIComponent(`${pathname}${search}`);
      window.location.replace(`/login?next=${next}`);
    };
    window.addEventListener("lipass:unauthorized", onUnauthorized);
    return () => {
      window.removeEventListener("lipass:unauthorized", onUnauthorized);
    };
  }, []);

  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
