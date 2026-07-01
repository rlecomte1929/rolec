// Space types for TypeScript support

import type { BrandPalette } from "@shared/schema";

export interface AppConfig {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  component: string;
  dataFile?: string;
  // When true, the EmailGate is bypassed for direct deep-link access via ?app=<id>.
  // Used for tokenised entrypoints where the app component itself validates the token.
  public?: boolean;
}

export interface TerminologyConfig {
  reading?: string;
  writing?: string;
  creating?: string;
  deleting?: string;
  editing?: string;
}

export interface DesktopTheme {
  gradient: string;
  accentColor: string;
  dockStyle: string;
}

export interface DesktopThemeTokens {
  palette?: BrandPalette;
  typography?: {
    headingFont?: string;
    bodyFont?: string;
    fontFamily?: string;
  };
  shell?: {
    accentColor?: string;
    dockStyle?: string;
    pageBackground?: string;
    gateBackground?: string;
    panelBackground?: string;
    panelStrongBackground?: string;
  };
  cssVariables?: Record<string, string>;
}

export interface DesktopLayout {
  agentPosition: string;
  dockPosition: string;
  appWindowSize: string;
}

export interface DesktopBranding {
  name: string;
  tagline?: string;
  logoUrl?: string;
  headingFont?: string;
  bodyFont?: string;
  colors?: Record<string, any>;
  palette?: Record<string, any>;
}

export interface DesktopConfig {
  theme: DesktopTheme;
  themeRecipe?: string;
  themeTokens?: DesktopThemeTokens;
  layout: DesktopLayout;
  branding: DesktopBranding;
}

export interface GenesisRuntimeTheme {
  branding: {
    name: string;
    tagline?: string;
    logoUrl?: string;
  };
  themeTokens: DesktopThemeTokens;
}

function buildFontFamily(fontName?: string): string {
  if (!fontName) {
    return '"Sora", system-ui, -apple-system, sans-serif';
  }

  return `"${fontName}", system-ui, -apple-system, sans-serif`;
}

export interface SpaceConfig {
  id: string;
  name: string;
  description?: string;
  version?: string;
  apps: AppConfig[];
  terminology?: TerminologyConfig;
  desktop: DesktopConfig;
}

export function resolveGenesisRuntimeTheme(
  config: SpaceConfig,
): GenesisRuntimeTheme {
  const branding = (config.desktop?.branding || {}) as DesktopBranding;
  const themeTokens = (config.desktop?.themeTokens || {}) as DesktopThemeTokens;
  const headingFont =
    themeTokens.typography?.headingFont ||
    branding.headingFont ||
    "Sora";
  const bodyFont =
    themeTokens.typography?.bodyFont ||
    branding.bodyFont ||
    headingFont;

  return {
    branding: {
      name: branding.name || config.name || "Welcome",
      tagline: branding.tagline,
      logoUrl:
        branding.logoUrl ||
        (config as any).iconUrl ||
        (config as any).logoUrl,
    },
    themeTokens: {
      palette: themeTokens.palette || branding.palette || branding.colors,
      typography: {
        headingFont,
        bodyFont,
        fontFamily:
          themeTokens.typography?.fontFamily || buildFontFamily(headingFont),
      },
      shell: themeTokens.shell,
      cssVariables: themeTokens.cssVariables || {},
    },
  };
}
