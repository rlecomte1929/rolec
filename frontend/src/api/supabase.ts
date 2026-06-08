import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    'Missing Supabase env vars: VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY must be set.'
  );
}

// Single app-wide Supabase client. Do NOT call createClient anywhere else:
// multiple instances share the sb-*-auth-token storage key and deadlock the
// Navigator LockManager (~10s timeouts on every login). Always import this.
export const supabase = createClient(supabaseUrl, supabaseAnonKey);
