// Imported dynamically, not statically. A static import here puts @supabase/supabase-js
// in the eager app-shell graph, which makes Vite emit a <link rel=modulepreload> for the
// 57 kB supabase-vendor chunk on every marketing page — downloaded by anonymous
// visitors who never authenticate. api/supabase.ts is UNCHANGED and still creates the
// client exactly once at module scope, so this resolves to the same singleton; multiple
// createClient instances would share the sb-*-auth-token key and deadlock the Navigator
// LockManager. Same pattern as components/NotificationsBell.tsx.

export interface DemoBookingInput {
  firstName: string;
  email: string;
  company: string;
  challenge: string;
  sourcePage?: string | null;
}

export interface DemoBookingSuccess {
  ok: true;
  demoId: string;
}

export interface DemoBookingFailure {
  ok: false;
  fieldErrors: Record<string, string>;
  formError: string | null;
}

export type DemoBookingResult = DemoBookingSuccess | DemoBookingFailure;

export async function submitDemoBooking(input: DemoBookingInput): Promise<DemoBookingResult> {
  try {
    const { supabase } = await import('./supabase');
    const invokeResult = await supabase.functions.invoke('submit-demo-request', {
      body: {
        firstName: input.firstName,
        email: input.email,
        company: input.company,
        challenge: input.challenge,
        sourcePage: input.sourcePage ?? null,
      },
    });
    const data = invokeResult.data as { ok?: boolean; demoId?: string } | null;
    const error: unknown = invokeResult.error;

    // Edge Function returned a non-2xx — supabase-js surfaces the response in `error.context`.
    if (error) {
      const parsed = await extractErrorBody(error);
      return {
        ok: false,
        fieldErrors: parsed.fieldErrors,
        formError: parsed.formError ?? 'Something went wrong. Please try again.',
      };
    }

    if (data?.ok === true && typeof data.demoId === 'string') {
      return { ok: true, demoId: data.demoId };
    }

    return {
      ok: false,
      fieldErrors: {},
      formError: 'Something went wrong. Please try again.',
    };
  } catch (err) {
    return {
      ok: false,
      fieldErrors: {},
      formError: err instanceof Error ? err.message : 'Network error. Please try again.',
    };
  }
}

async function extractErrorBody(
  error: unknown
): Promise<{ fieldErrors: Record<string, string>; formError: string | null }> {
  const ctx = (error as { context?: Response | undefined })?.context;
  if (!ctx || typeof ctx.text !== 'function') {
    return { fieldErrors: {}, formError: null };
  }
  try {
    const raw = await ctx.text();
    const parsed = JSON.parse(raw) as { errors?: Record<string, string>; error?: string };
    const { _form, ...fieldErrors } = parsed.errors ?? {};
    return {
      fieldErrors,
      formError: _form ?? parsed.error ?? null,
    };
  } catch {
    return { fieldErrors: {}, formError: null };
  }
}
