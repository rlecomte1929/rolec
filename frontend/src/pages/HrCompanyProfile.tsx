import React, { useEffect, useState, useCallback } from 'react';
import { AppShell } from '../components/AppShell';
import { Card, Button, Input, Alert } from '../components/antigravity';
import { hrAPI } from '../api/client';
import { useNavigate, useLocation } from 'react-router-dom';
import { safeNavigate } from '../navigation/safeNavigate';
import { useCompany } from '../hooks/useCompany';
import { trackAuthPerf } from '../perf/authPerf';
import type { CompanyProfilePayload } from '../types';

const ACCEPT_TYPES = 'image/png,image/jpeg,image/jpg,image/svg+xml';
const MAX_SIZE_BYTES = 2 * 1024 * 1024; // 2MB

/** Skeleton placeholder for form fields while profile loads. */
const FieldSkeleton = () => (
  <div className="h-10 rounded-lg bg-[#e2e8f0] animate-pulse" />
);

export const HrCompanyProfile: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { company, refresh: refreshCompany } = useCompany();
  const [name, setName] = useState('');
  const [country, setCountry] = useState('');
  const [sizeBand, setSizeBand] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [hrContact, setHrContact] = useState('');
  const [legalName, setLegalName] = useState('');
  const [website, setWebsite] = useState('');
  const [hqCity, setHqCity] = useState('');
  const [industry, setIndustry] = useState('');
  const [defaultDestinationCountry, setDefaultDestinationCountry] = useState('');
  const [supportEmail, setSupportEmail] = useState('');
  const [defaultWorkingLocation, setDefaultWorkingLocation] = useState('');
  const [profileLoading, setProfileLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [logoError, setLogoError] = useState('');
  const [logoUploading, setLogoUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
    trackAuthPerf({ stage: 'bootstrap_start', route: location.pathname });

    hrAPI.getCompanyProfile()
      .then((res) => {
        if (res.company) {
          const c = res.company as Record<string, unknown>;
          setName((c.name as string) || '');
          setCountry((c.country as string) || '');
          setSizeBand((c.size_band as string) || '');
          setAddress((c.address as string) || '');
          setPhone((c.phone as string) || '');
          setHrContact((c.hr_contact as string) || '');
          setLegalName((c.legal_name as string) || '');
          setWebsite((c.website as string) || '');
          setHqCity((c.hq_city as string) || '');
          setIndustry((c.industry as string) || '');
          setDefaultDestinationCountry((c.default_destination_country as string) || '');
          setSupportEmail((c.support_email as string) || '');
          setDefaultWorkingLocation((c.default_working_location as string) || '');
        }
      })
      .catch((err: { response?: { status?: number; data?: { detail?: string } } }) => {
        if (err?.response?.status === 401) safeNavigate(navigate, 'landing');
      })
      .finally(() => {
        setProfileLoading(false);
        const dur = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0;
        trackAuthPerf({ stage: 'bootstrap_end', route: location.pathname, durationMs: dur });
      });
  }, [navigate, location.pathname]);

  const validateLogo = (file: File): string | null => {
    const allowed = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml'];
    if (!allowed.includes(file.type)) {
      return 'Use PNG, JPG, or SVG.';
    }
    if (file.size > MAX_SIZE_BYTES) {
      return 'Logo must be 2MB or smaller.';
    }
    return null;
  };

  const handleLogoFile = useCallback(
    async (file: File) => {
      setLogoError('');
      const err = validateLogo(file);
      if (err) {
        setLogoError(err);
        return;
      }
      setLogoUploading(true);
      try {
        await hrAPI.uploadCompanyLogo(file);
        await refreshCompany();
      } catch (e: unknown) {
        const msg = e && typeof e === 'object' && 'response' in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : 'Upload failed.';
        setLogoError(typeof msg === 'string' ? msg : 'Upload failed.');
      } finally {
        setLogoUploading(false);
      }
    },
    [refreshCompany]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer?.files?.[0];
      if (file) handleLogoFile(file);
    },
    [handleLogoFile]
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const removeLogo = async () => {
    setLogoError('');
    setLogoUploading(true);
    try {
      await hrAPI.removeCompanyLogo();
      await refreshCompany();
    } catch {
      setLogoError('Failed to remove logo.');
    } finally {
      setLogoUploading(false);
    }
  };

  const save = async () => {
    if (!name.trim()) {
      setError('Company name is required.');
      return;
    }
    setError('');
    setSaved(false);
    setSaving(true);
    try {
      const payload: CompanyProfilePayload = {
        name: name.trim(),
        country: country.trim() || undefined,
        size_band: sizeBand.trim() || undefined,
        address: address.trim() || undefined,
        phone: phone.trim() || undefined,
        hr_contact: hrContact.trim() || undefined,
        legal_name: legalName.trim() || undefined,
        website: website.trim() || undefined,
        hq_city: hqCity.trim() || undefined,
        industry: industry.trim() || undefined,
        default_destination_country: defaultDestinationCountry.trim() || undefined,
        support_email: supportEmail.trim() || undefined,
        default_working_location: defaultWorkingLocation.trim() || undefined,
      };
      await hrAPI.saveCompanyProfile(payload);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: unknown) {
      const d = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : 'Failed to save company profile.';
      setError(typeof d === 'string' ? d : 'Failed to save company profile.');
    } finally {
      setSaving(false);
    }
  };

  const logoUrl = company?.logo_url ?? null;

  return (
    <AppShell title="Company Profile" subtitle={profileLoading ? 'Loading...' : 'Complete your company profile to prefill employee cases.'}>
      <Card padding="lg">
        {error && <Alert variant="error" className="mb-4">{error}</Alert>}
        {saved && <Alert variant="success" className="mb-4">Saved.</Alert>}
        <div className="space-y-4">
          {profileLoading ? (
            <>
              {[...Array(12)].map((_, i) => <FieldSkeleton key={i} />)}
              <div className="pt-2">
                <div className="h-4 w-40 rounded bg-[#e2e8f0] animate-pulse mb-2" />
                <div className="h-24 rounded-lg bg-[#e2e8f0] animate-pulse" />
              </div>
            </>
          ) : (
          <>
          <Input label="Company name" value={name} onChange={setName} fullWidth />
          <Input label="Legal name" value={legalName} onChange={setLegalName} fullWidth placeholder="Optional" />
          <Input label="Country" value={country} onChange={setCountry} fullWidth />
          <Input label="HQ city" value={hqCity} onChange={setHqCity} fullWidth placeholder="Optional" />
          <Input label="Company size band" value={sizeBand} onChange={setSizeBand} placeholder="e.g. 50-200" fullWidth />
          <Input label="Industry" value={industry} onChange={setIndustry} fullWidth placeholder="Optional" />
          <Input label="Website" value={website} onChange={setWebsite} fullWidth placeholder="https://..." />
          <Input label="Address" value={address} onChange={setAddress} fullWidth />
          <Input label="Phone" value={phone} onChange={setPhone} fullWidth />
          <Input label="HR contact" value={hrContact} onChange={setHrContact} placeholder="e.g. hr@company.com" fullWidth />
          <Input label="Default destination country" value={defaultDestinationCountry} onChange={setDefaultDestinationCountry} fullWidth placeholder="Optional" />
          <Input label="Support / HR contact email" value={supportEmail} onChange={setSupportEmail} fullWidth placeholder="Optional" />
          <Input label="Default working location" value={defaultWorkingLocation} onChange={setDefaultWorkingLocation} fullWidth placeholder="Optional" />

          <div className="pt-2">
            <label className="block text-sm font-medium text-[#374151] mb-2">Company logo</label>
            <p className="text-xs text-[#6b7280] mb-2">PNG, JPG or SVG, max 2MB. Recommended: square 512×512.</p>
            {logoUrl ? (
              <div className="flex items-center gap-4">
                <img src={logoUrl} alt="Company logo" className="h-16 w-16 rounded-lg object-cover border border-[#e2e8f0]" />
                <Button type="button" variant="secondary" onClick={removeLogo} disabled={logoUploading}>
                  {logoUploading ? 'Removing…' : 'Remove logo'}
                </Button>
              </div>
            ) : (
              <div
                onDrop={onDrop}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${dragOver ? 'border-[#1d4ed8] bg-[#eff6ff]' : 'border-[#e2e8f0] bg-[#f8fafc]'}`}
              >
                <input
                  type="file"
                  accept={ACCEPT_TYPES}
                  className="hidden"
                  id="logo-upload"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleLogoFile(f);
                    e.target.value = '';
                  }}
                />
                <p className="text-sm text-[#6b7280] mb-2">Drag & drop a logo here, or</p>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={logoUploading}
                  onClick={() => document.getElementById('logo-upload')?.click()}
                >
                  {logoUploading ? 'Uploading…' : 'Upload logo'}
                </Button>
              </div>
            )}
            {logoError && <p className="text-sm text-red-600 mt-2">{logoError}</p>}
          </div>

          <Button onClick={save} disabled={saving}>
            {saving ? 'Saving...' : 'Save company profile'}
          </Button>
          </>
          )}
        </div>
      </Card>
    </AppShell>
  );
};
