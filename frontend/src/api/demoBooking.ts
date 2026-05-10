import { supabase } from './supabase';

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
    const { data, error } = await supabase.functions.invoke('submit-demo-request', {
      body: {
        firstName: input.firstName,
        email: input.email,
        company: input.company,
        challenge: input.challenge,
        sourcePage: input.sourcePage ?? null,
      },
    });

    // Edge Function returned a non-2xx — supabase-js surfaces the response in `error.context`.
    if (error) {
      const parsed = await extractErrorBody(error);
      return {
        ok: false,
        fieldErrors: parsed.fieldErrors,
        formError: parsed.formError ?? 'Something went wrong. Please try again.',
      };
    }

    if (data && typeof data === 'object' && 'ok' in data && data.ok === true && typeof (data as any).demoId === 'string') {
      return { ok: true, demoId: (data as any).demoId };
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
