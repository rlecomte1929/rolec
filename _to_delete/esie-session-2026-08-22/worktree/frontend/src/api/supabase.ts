import { createClient } from '@supabase/supabase-js';
import { env } from '../config/env';

// Single app-wide Supabase client. Do NOT call createClient anywhere else:
// multiple instances share the sb-*-auth-token storage key and deadlock the
// Navigator LockManager (~10s timeouts on every login). Always import this.
// Required-env validation (the throw on missing URL/anon key) lives in config/env.
// [AIQ-1491] experimental.passkey enables auth.signInWithPasskey()/registerPasskey()
// (auth-js 2.108). Defaults to false — passkey methods throw a descriptive error at call
// time without it. Additive: does not affect the existing password / OAuth flows. Requires
// WebAuthn enabled on the Supabase project (staging + Pro) for the ceremony to succeed.
export const supabase = createClient(env.supabaseUrl, env.supabaseAnonKey, {
  auth: { experimental: { passkey: true } },
});
