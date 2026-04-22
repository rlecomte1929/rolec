/**
 * Public endpoint for demo-booking leads from the landing pages.
 * Validates input, stores a row in `demo_requests`, and emails romain.lecomte@relopass.com.
 * Env: DEMO_NOTIFY_TO (default romain.lecomte@relopass.com),
 *      EMAIL_PROVIDER (resend|stub), EMAIL_API_KEY, EMAIL_FROM.
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const MAX_FIRST_NAME = 80;
const MAX_COMPANY = 120;
const MAX_CHALLENGE = 500;
const MAX_SOURCE_PAGE = 120;

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

interface DemoRequestPayload {
  firstName: string;
  email: string;
  company: string;
  challenge: string;
  sourcePage?: string;
}

interface ValidationResult {
  ok: boolean;
  errors: Record<string, string>;
  cleaned?: {
    firstName: string;
    email: string;
    company: string;
    challenge: string;
    sourcePage: string | null;
  };
}

function isEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function validate(body: unknown): ValidationResult {
  const errors: Record<string, string> = {};
  if (!body || typeof body !== "object") {
    return { ok: false, errors: { _form: "Invalid request body." } };
  }
  const b = body as Partial<DemoRequestPayload>;
  const firstName = (b.firstName ?? "").trim();
  const email = (b.email ?? "").trim();
  const company = (b.company ?? "").trim();
  const challenge = (b.challenge ?? "").trim();
  const sourcePage = (b.sourcePage ?? "").trim().slice(0, MAX_SOURCE_PAGE) || null;

  if (firstName.length < 2) errors.firstName = "Please enter your first name.";
  else if (firstName.length > MAX_FIRST_NAME) errors.firstName = "First name is too long.";

  if (!isEmail(email)) errors.email = "Please enter a valid email address.";

  if (company.length < 2) errors.company = "Please enter your company name.";
  else if (company.length > MAX_COMPANY) errors.company = "Company name is too long.";

  if (challenge.length < 10) errors.challenge = "Tell us a bit more (min 10 characters).";
  else if (challenge.length > MAX_CHALLENGE) errors.challenge = "Please keep this under 500 characters.";

  if (Object.keys(errors).length > 0) {
    return { ok: false, errors };
  }

  return {
    ok: true,
    errors: {},
    cleaned: { firstName, email, company, challenge, sourcePage },
  };
}

async function sendResendEmail(
  to: string,
  subject: string,
  text: string,
  html: string,
  apiKey: string,
  from: string,
  replyTo: string | null
): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      from,
      to: [to],
      subject,
      text,
      html,
      ...(replyTo ? { reply_to: replyTo } : {}),
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    return { ok: false, error: `Resend ${res.status}: ${err}` };
  }
  return { ok: true };
}

async function notify(
  to: string,
  data: { firstName: string; email: string; company: string; challenge: string; sourcePage: string | null; demoId: string }
): Promise<{ ok: boolean; error?: string }> {
  const provider = Deno.env.get("EMAIL_PROVIDER") || "stub";
  const apiKey = Deno.env.get("EMAIL_API_KEY") || "";
  const from = Deno.env.get("EMAIL_FROM") || "notifications@relopass.com";

  const subject = `Demo request — ${data.firstName} @ ${data.company}`;
  const text = [
    `${data.firstName} from ${data.company} requested a demo.`,
    ``,
    `Email: ${data.email}`,
    `Source: ${data.sourcePage ?? "unknown"}`,
    `Demo ID: ${data.demoId}`,
    ``,
    `Challenge:`,
    data.challenge,
  ].join("\n");
  const html = `
    <h2 style="margin:0 0 12px;font-family:Inter,system-ui,sans-serif;color:#0c1929;">Demo request</h2>
    <p style="margin:0 0 16px;font-family:Inter,system-ui,sans-serif;color:#1a2734;">
      <strong>${escapeHtml(data.firstName)}</strong> from <strong>${escapeHtml(data.company)}</strong> requested a demo.
    </p>
    <table style="border-collapse:collapse;font-family:Inter,system-ui,sans-serif;font-size:14px;color:#1a2734;">
      <tr><td style="padding:4px 16px 4px 0;color:#4a5f73;">Email</td><td>${escapeHtml(data.email)}</td></tr>
      <tr><td style="padding:4px 16px 4px 0;color:#4a5f73;">Source</td><td>${escapeHtml(data.sourcePage ?? "unknown")}</td></tr>
      <tr><td style="padding:4px 16px 4px 0;color:#4a5f73;">Demo ID</td><td>${escapeHtml(data.demoId)}</td></tr>
    </table>
    <p style="margin:16px 0 4px;font-family:Inter,system-ui,sans-serif;color:#4a5f73;font-size:13px;">Challenge:</p>
    <blockquote style="margin:0;padding:12px 16px;background:#f8fafb;border-left:3px solid #197b78;font-family:Inter,system-ui,sans-serif;color:#1a2734;white-space:pre-wrap;">${escapeHtml(data.challenge)}</blockquote>
  `;

  if (provider === "resend") {
    return sendResendEmail(to, subject, text, html, apiKey, from, data.email);
  }

  console.log("[submit-demo-request] STUB notify:", { to, subject });
  return { ok: true };
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }
  if (req.method !== "POST") {
    return Response.json({ ok: false, error: "Method not allowed" }, { status: 405, headers: CORS_HEADERS });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ ok: false, error: "Invalid JSON." }, { status: 400, headers: CORS_HEADERS });
  }

  const validation = validate(body);
  if (!validation.ok || !validation.cleaned) {
    return Response.json(
      { ok: false, errors: validation.errors },
      { status: 400, headers: CORS_HEADERS }
    );
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const supabase = createClient(supabaseUrl, serviceKey);

  const userAgent = req.headers.get("user-agent")?.slice(0, 300) ?? null;

  const { data: inserted, error: insertError } = await supabase
    .from("demo_requests")
    .insert({
      first_name: validation.cleaned.firstName,
      email: validation.cleaned.email,
      company: validation.cleaned.company,
      challenge: validation.cleaned.challenge,
      source_page: validation.cleaned.sourcePage,
      user_agent: userAgent,
    })
    .select("id")
    .single();

  if (insertError || !inserted) {
    console.error("[submit-demo-request] Insert error:", insertError);
    return Response.json(
      { ok: false, error: "Could not save your request. Please try again." },
      { status: 500, headers: CORS_HEADERS }
    );
  }

  const notifyTo = Deno.env.get("DEMO_NOTIFY_TO") || "romain.lecomte@relopass.com";
  const result = await notify(notifyTo, {
    ...validation.cleaned,
    demoId: inserted.id as string,
  });

  if (!result.ok) {
    console.error("[submit-demo-request] Notify failed:", result.error);
    // Row is saved; still surface success to the user so the lead isn't lost if email is transiently down.
  }

  return Response.json(
    { ok: true, demoId: inserted.id },
    { headers: CORS_HEADERS }
  );
});
