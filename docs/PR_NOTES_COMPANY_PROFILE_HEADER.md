# PR: Company Profile + unified header with company branding

## Summary

- **HR** can manage company profile (name, logo, legal name, website, HQ, industry, default relocation fields) and upload/remove company logo.
- **Header** is unified for HR and Employee: same structure with **Company logo + company name** on the top-right, next to notification bell and user menu.
- **Employees** see the same company branding in read-only form (no edit/upload).

## What changed

### Backend

- **Database**
  - `database.py`: `create_company()` extended with optional `legal_name`, `website`, `hq_city`, `industry`, `logo_url`, `brand_color`, `default_destination_country`, `support_email`, `default_working_location`; added `update_company_logo(company_id, logo_url)`.
- **API**
  - `CompanyProfileRequest` and `save_company_profile` accept the new company profile fields.
  - **GET `/api/company`**: returns the current user’s company (for header); available to any authenticated user (HR/Employee/Admin).
  - **POST `/api/hr/company-profile/logo`**: multipart file upload → Supabase Storage `company-logos/companies/{company_id}/logo.{ext}` → sets `companies.logo_url` to public URL.
  - **POST `/api/hr/company-profile/remove-logo`**: sets `companies.logo_url` to null.
- Logo upload: PNG/JPG/SVG, max 2MB; uses `get_supabase_admin_client()` and public URL.

### Frontend

- **API client**
  - `companyAPI.get()` for GET `/api/company`.
  - `hrAPI.saveCompanyProfile(payload)` extended with new fields (`CompanyProfilePayload`).
  - `hrAPI.uploadCompanyLogo(file)` and `hrAPI.removeCompanyLogo()`.
- **Types**
  - `Company` and `CompanyProfilePayload` in `types.ts`.
- **useCompany()**
  - Fetches GET `/api/company`, returns `{ company, loading, refresh }`; used for header and HR profile.
- **CompanyBrand**
  - Header block: small circular logo (or initials badge) + company name (truncated); renders only when company is loaded.
- **AppShell**
  - Header right: **CompanyBrand** then NotificationBell then user menu (same for HR and Employee).
- **HrCompanyProfile**
  - Form: company name, legal name, country, HQ city, size band, industry, website, address, phone, HR contact, default destination country, support email, default working location.
  - Logo: drag-and-drop + “Upload logo” button, PNG/JPG/SVG max 2MB, preview and “Remove logo”; success/error feedback and save “Saved” message.

### Existing artifacts

- Supabase migration and storage doc were already in place (`docs/COMPANY_LOGOS_STORAGE.md`). Backend uses the same bucket/path and public URL pattern.

## Why

- Single place for HR to set company identity and basic relocation defaults.
- Consistent top ribbon for HR and Employee with company branding.
- Employees see their company’s logo/name without edit access; RLS/role checks enforce read-only for employees and upload/update only for HR.

## How to verify

1. **HR**: Open `/hr/company-profile`, set name and optional fields, upload a logo (PNG/JPG/SVG ≤2MB), save → header shows logo + name; remove logo → header shows initials.
2. **Employee**: Log in as employee linked to same company → header shows same company logo + name (no Company Profile nav).
3. **Header**: Same layout and CompanyBrand placement on HR and Employee pages; no layout shift when company loads.
