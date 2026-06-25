import { createClient } from '@supabase/supabase-js';
import { env } from '../config/env';

// Single app-wide Supabase client. Do NOT call createClient anywhere else:
// multiple instances share the sb-*-auth-token storage key and deadlock the
// Navigator LockManager (~10s timeouts on every login). Always import this.
// Required-env validation (the throw on missing URL/anon key) lives in config/env.
export const supabase = createClient(env.supabaseUrl, env.supabaseAnonKey);
