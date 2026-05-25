/**
 * get-feature-flags — Supabase Edge Function (PRODUCT-6A) v7
 * ─────────────────────────────────────────────────────────────────────────────
 * Safe proxy for Vercel Edge Config feature flags.
 * The browser never receives the EDGE_CONFIG token — all reads go server-side.
 *
 * Usage (frontend):
 *   GET /functions/v1/get-feature-flags
 *   → { flags: { onboarding_flow_v2: { enabled: true, ... }, ... } }
 *
 * Usage (curl):
 *   curl https://<project>.supabase.co/functions/v1/get-feature-flags
 *   (no Authorization header required — verify_jwt: false)
 *
 * Environment variables (set in Supabase vault):
 *   EDGE_CONFIG   — Vercel Edge Config connection string
 *                   Format: https://edge-config.vercel.com/<id>?token=<token>
 *                   (short ecfg_<token> form is NOT supported)
 *
 * If EDGE_CONFIG is not set or unreachable, falls back to safe defaults (all flags disabled).
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

/** Safe defaults — all flags off. Used when Edge Config is unavailable. */
const FLAG_DEFAULTS: Record<string, FeatureFlag> = {
  onboarding_flow_v2: {
    enabled: false,
    variants: ["control", "variant_a"],
    traffic_split: [100, 0],
    description: "New onboarding flow with progress bar and inline validation.",
  },
  hr_policy_assistant_v2: {
    enabled: false,
    variants: ["control", "variant_a"],
    traffic_split: [100, 0],
    description: "Redesigned HR policy assistant with streaming responses and source citations.",
  },
  employee_dashboard_v2: {
    enabled: false,
    variants: ["control", "variant_a"],
    traffic_split: [100, 0],
    description: "Platform V2 employee dashboard.",
  },
};

interface FeatureFlag {
  enabled: boolean;
  variants: string[];
  traffic_split: number[];
  description?: string;
}

interface FlagsPayload {
  flags: Record<string, FeatureFlag>;
}

/**
 * Parse the EDGE_CONFIG env var into a usable REST URL.
 * Only the full URL form is supported:
 *   https://edge-config.vercel.com/<id>?token=<token>
 * The short ecfg_<token> form does NOT contain enough info to build a URL.
 */
function buildEdgeConfigUrl(connectionString: string): string | null {
  if (connectionString.startsWith("https://edge-config.vercel.com/")) {
    const base = connectionString.replace(/\/$/, "");
    return `${base}/item/flags`;
  }
  console.warn("[get-feature-flags] EDGE_CONFIG must be the full URL form (https://edge-config.vercel.com/...). Short ecfg_ form is not supported.");
  return null;
}

async function readFlagsFromEdgeConfig(connectionString: string): Promise<Record<string, FeatureFlag> | null> {
  const url = buildEdgeConfigUrl(connectionString);
  if (!url) {
    console.warn("[get-feature-flags] EDGE_CONFIG format not recognised; using defaults.");
    return null;
  }

  try {
    const res = await fetch(url, {
      headers: { "Accept": "application/json" },
    });

    if (!res.ok) {
      console.warn(`[get-feature-flags] Edge Config returned ${res.status}; using defaults.`);
      return null;
    }

    const payload = await res.json() as Record<string, FeatureFlag> | null;
    if (!payload || typeof payload !== "object") {
      console.warn("[get-feature-flags] Edge Config 'flags' value is not an object; using defaults.");
      return null;
    }
    return payload;
  } catch (err) {
    console.warn("[get-feature-flags] Failed to reach Edge Config:", err);
    return null;
  }
}

serve(async (req: Request) => {
  // CORS pre-flight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }

  try {
    const connectionString = Deno.env.get("EDGE_CONFIG") ?? "";
    let flags: Record<string, FeatureFlag>;

    if (connectionString) {
      const remote = await readFlagsFromEdgeConfig(connectionString);
      // Merge: remote values override defaults, so new flags added to remote
      // are picked up without a code deploy.
      flags = { ...FLAG_DEFAULTS, ...(remote ?? {}) };
    } else {
      console.info("[get-feature-flags] EDGE_CONFIG not set; serving defaults.");
      flags = { ...FLAG_DEFAULTS };
    }

    const body: FlagsPayload = { flags };

    return new Response(JSON.stringify(body), {
      headers: {
        ...CORS_HEADERS,
        "Content-Type": "application/json",
        // no-store: always fetch fresh flags — avoids CDN serving stale flag state
        "Cache-Control": "no-store",
      },
    });
  } catch (err) {
    console.error("[get-feature-flags] Unexpected error:", err);
    return new Response(
      JSON.stringify({ flags: FLAG_DEFAULTS, _error: "Edge Config unavailable; using defaults." }),
      {
        status: 200, // still return 200 with defaults so the app never hard-fails on flags
        headers: { ...CORS_HEADERS, "Content-Type": "application/json", "Cache-Control": "no-store" },
      }
    );
  }
});
