import { Route, Routes } from "react-router-dom";

import { LoginPage } from "./pages/LoginPage";
import { PanelPage } from "./pages/PanelPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SetupPage } from "./pages/SetupPage";
import { SsoLinkPage } from "./pages/SsoLinkPage";
import { ToastProvider } from "./components/Toast";

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/" element={<PanelPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/sso/link" element={<SsoLinkPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </ToastProvider>
  );
}
