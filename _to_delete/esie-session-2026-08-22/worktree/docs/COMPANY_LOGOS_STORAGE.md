# Company logos storage (Supabase)

## Bucket

- **Name:** `company-logos`
- **Public:** Yes (MVP) so logo URLs work without signed URLs. Alternatively use private bucket + signed URLs.

## Path

- `companies/{company_id}/logo.{ext}` — e.g. `companies/demo-company-001/logo.png`

## Setup (Supabase Dashboard)

1. Storage → New bucket → name: `company-logos`, set **Public** if you want direct logo URLs.
2. Policies:
   - **Select (read):** Allow public read if bucket is public; or allow authenticated users whose profile has the same `company_id` (requires RLS on storage.objects).
   - **Insert/Update:** Allow only if `auth.uid()` matches an HR/Admin profile for that company (e.g. folder name = company_id and profile.company_id = company_id).

## MVP (backend upload)

If the app uploads via the backend (service role), the backend can upload to `company-logos/companies/{company_id}/logo.png` and store the public URL in `companies.logo_url`. No client-side storage RLS needed for upload.

## Policy examples (when using Supabase Auth)

- **Read:** `bucket_id = 'company-logos'` and (public or true for authenticated).
- **Upload:** `bucket_id = 'company-logos'` and (storage.foldername() = array['companies', company_id] and profile.role in ('hr','admin')).
