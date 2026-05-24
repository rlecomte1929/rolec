/**
 * get-feature-flags — Supabase Edge Function (PRODUCT-6A)
 * ─────────────────────────────────────────────────────────────────────────────
 * Safe proxy for Vercel Edge Config feature flags.
 * The browser never receives the EDGE_CONFIG token — all reads go server-side.
 *
 * Usage (frontend):
 *   GET /functions/v1/get-feature-flags
 *   → { flags: { onboarding_flow_v2: { enabled: false, ... }, ... } }
 *
 * Usage (curl):
 *   curl https://<project>.supabase.co/functions/v1/get-feature-flags \
 *     -H "Authorization: Bearer <anon-key>"
 *
 * Environment variables (set in Supabase vault):
 *   EDGE_CONFIG   — Vercel Edge Config connection string
 *                   Format: https://edge-config.vercel.com/<id>?token=<token>
 *                   OR the short form: ecfg_<token>
 *
 * If EDGE_CONFIG is not set, falls back to safe defaults (all flags disabled).
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
 * Vercel Edge Config connection strings come in two forms:
 *   1. Full URL: https://edge-config.vercel.com/<id>?token=<token>
 *   2. Short:    ecfg_<token>  (not enough info to build URL — treat as missing)
 */
function buildEdgeConfigUrl(connectionString: string): string | null {
  if (connectionString.startsWith("https://edge-config.vercel.com/")) {
    // Already a full URL — append /item/flags to read the flags key
    const base = connectionString.replace(/\/$/, "");
    return `${base}/item/flags`;
  }
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
        // Cache for 60 s on the CDN — flags don't change per-request
        "Cache-Control": "public, max-age=60, stale-while-revalidate=30",
      },
    });
  } catch (err) {
    console.error("[get-feature-flags] Unexpected error:", err);
    return new Response(
      JSON.stringify({ flags: FLAG_DEFAULTS, _error: "Edge Config unavailable; using defaults." }),
      {
        status: 200, // still return 200 with defaults so the app never hard-fails on flags
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      }
    );
  }
});
