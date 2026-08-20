import type { ReactNode } from "react";

import { BRAND } from "../lib/brand";
import { AuroraBackground } from "./AuroraBackground";
import { BlurText } from "./BlurText";
import { FloatingBackground } from "./FloatingBackground";
import { TechAmbience } from "./TechAmbience";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen bg-background">
      <AuroraBackground />
      <FloatingBackground shapeCount={10} />
      <TechAmbience />
      <div className="relative z-10 flex min-h-screen items-center justify-center px-4 py-10">
        <div className="card card-halo w-full max-w-md p-6 sm:p-8">
          <div className="mb-6 flex flex-col items-center gap-3 text-center">
            <span className="brand-halo">
              <img src={BRAND.logo} alt="" className="h-12 w-12 rounded-2xl" />
            </span>
            <div>
              <h1 className="text-xl font-semibold text-foreground">
                <BlurText text={BRAND.name} />
              </h1>
              <p className="mt-1 text-sm text-muted">{BRAND.slogan}</p>
            </div>
          </div>
          {children}
          <p className="mt-8 text-center text-xs text-muted">
            {BRAND.footerText}
            {BRAND.icp ? ` · ${BRAND.icp}` : ""}
          </p>
        </div>
      </div>
    </div>
  );
}
