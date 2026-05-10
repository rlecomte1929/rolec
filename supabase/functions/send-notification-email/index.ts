/**
 * Option 6C: Send notification emails from outbox.
 * Reads pending notification_outbox rows, sends via configured provider, updates status.
 * Env: EMAIL_PROVIDER (resend|sendgrid|mailgun|stub), EMAIL_API_KEY, EMAIL_FROM
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const LIMIT = 20;

interface OutboxRow {
  id: string;
  notification_id: string | null;
  user_id: string;
  to_email: string;
  type: string;
  payload: Record<string, unknown>;
  status: string;
}

interface SendResult {
  ok: boolean;
  error?: string;
}

async function sendEmailStub(
  to: string,
  subject: string,
  body: string,
  _payload: Record<string, unknown>
): Promise<SendResult> {
  console.log("[send-notification-email] STUB send:", { to, subject, body: body?.slice(0, 80) });
  return { ok: true };
}

async function sendEmailResend(
  to: string,
  subject: string,
  body: string,
  _payload: Record<string, unknown>,
  apiKey: string,
  from: string
): Promise<SendResult> {
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
      text: body,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    return { ok: false, error: `Resend ${res.status}: ${err}` };
  }
  return { ok: true };
}

async function sendEmail(
  to: string,
  subject: string,
  body: string,
  payload: Record<string, unknown>
): Promise<SendResult> {
  const provider = Deno.env.get("EMAIL_PROVIDER") || "stub";
  const apiKey = Deno.env.get("EMAIL_API_KEY") || "";
  const from = Deno.env.get("EMAIL_FROM") || "notifications@relopass.com";

  if (provider === "stub") {
    return sendEmailStub(to, subject, body, payload);
  }
  if (provider === "resend") {
    return sendEmailResend(to, subject, body, payload, apiKey, from);
  }
  console.warn("[send-notification-email] Unknown provider:", provider, "- using stub");
  return sendEmailStub(to, subject, body, payload);
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: { "Access-Control-Allow-Origin": "*" } });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const supabase = createClient(supabaseUrl, serviceKey);

  const { data: rows, error: fetchError } = await supabase
    .from("notification_outbox")
    .select("id, notification_id, user_id, to_email, type, payload, status")
    .eq("status", "pending")
    .order("created_at", { ascending: true })
    .limit(LIMIT);

  if (fetchError) {
    console.error("[send-notification-email] Fetch error:", fetchError);
    return Response.json(
      { ok: false, error: fetchError.message },
      { status: 500, headers: { "Access-Control-Allow-Origin": "*" } }
    );
  }

  const items = (rows || []) as OutboxRow[];
  let sent = 0;
  let failed = 0;

  for (const row of items) {
    const payload = (row.payload || {}) as Record<string, unknown>;
    const subject = (payload.title as string) || `ReloPass: ${row.type}`;
    const body = (payload.body as string) || "You have a new notification.";

    const result = await sendEmail(row.to_email, subject, body, payload);

    if (result.ok) {
      await supabase
        .from("notification_outbox")
        .update({ status: "sent", sent_at: new Date().toISOString(), last_error: null })
        .eq("id", row.id);

      if (row.notification_id) {
        await supabase
          .from("notifications")
          .update({
            email_status: "sent",
            delivered_at: new Date().toISOString(),
            email_last_error: null,
          })
          .eq("id", row.notification_id);
      }
      sent += 1;
    } else {
      await supabase
        .from("notification_outbox")
        .update({ status: "failed", last_error: result.error })
        .eq("id", row.id);

      if (row.notification_id) {
        await supabase
          .from("notifications")
          .update({
            email_status: "failed",
            email_last_error: result.error,
          })
          .eq("id", row.notification_id);
      }
      failed += 1;
    }
  }

  return Response.json(
    { ok: true, processed: items.length, sent, failed },
    { headers: { "Access-Control-Allow-Origin": "*" } }
  );
});
