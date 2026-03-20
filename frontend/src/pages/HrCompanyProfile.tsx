import React, { useEffect, useState, useCallback } from 'react';
import { AppShell } from '../components/AppShell';
import { Card, Button, Input, Alert } from '../components/antigravity';
import { hrAPI } from '../api/client';
import { useLocation } from 'react-router-dom';
import { trackAuthPerf } from '../perf/authPerf';
import { trackRouteEntry, trackShellRender, trackFirstMeaningfulContent } from '../perf/pagePerf';
import { useHrCompanyContext } from '../contexts/HrCompanyContext';
import type { CompanyProfilePayload } from '../types';

const ACCEPT_TYPES = 'image/png,image/jpeg,image/jpg,image/svg+xml';
const MAX_SIZE_BYTES = 2 * 1024 * 1024; // 2MB

/** Skeleton placeholder for form fields while profile loads. */
const FieldSkeleton = () => (
  <div className="h-10 rounded-lg bg-[#e2e8f0] animate-pulse" />
);

export const HrCompanyProfile: React.FC = () => {
  const location = useLocation();
  const route = location.pathname;
  const { company, loading: profileLoading, error: contextError, refresh } = useHrCompanyContext();

  useEffect(() => {
    trackRouteEntry(route);
    trackShellRender(route);
  }, [route]);

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
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [logoError, setLogoError] = useState('');
  const [logoUploading, setLogoUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    if (company) {
      const c = company as Record<string, unknown>;
      const pick = (snake: string, camel: string) =>
        String((c[snake] ?? c[camel] ?? '') || '').trim();
      setName(pick('name', 'name'));
      setCountry(pick('country', 'country'));
      setSizeBand(pick('size_band', 'sizeBand'));
      setAddress(pick('address', 'address'));
      setPhone(pick('phone', 'phone'));
      setHrContact(pick('hr_contact', 'hrContact'));
      setLegalName(pick('legal_name', 'legalName'));
      setWebsite(pick('website', 'website'));
      setHqCity(pick('hq_city', 'hqCity'));
      setIndustry(pick('industry', 'industry'));
      setDefaultDestinationCountry(pick('default_destination_country', 'defaultDestinationCountry'));
      setSupportEmail(pick('support_email', 'supportEmail'));
      setDefaultWorkingLocation(pick('default_working_location', 'defaultWorkingLocation'));
      const logo = pick('logo_url', 'logoUrl');
      setLogoUrl(logo || null);

      const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
      trackAuthPerf({ stage: 'bootstrap_end', route: location.pathname, durationMs: t0 });
      trackFirstMeaningfulContent(location.pathname, t0);
    }
  }, [company, location.pathname]);

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
        await refresh();
        // Context will update; useEffect syncs company -> form state including logoUrl
      } catch (e: unknown) {
        const msg = e && typeof e === 'object' && 'response' in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : 'Upload failed.';
        setLogoError(typeof msg === 'string' ? msg : 'Upload failed.');
      } finally {
        setLogoUploading(false);
      }
    },
    [refresh]
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
      await refresh();
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
      await refresh();
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


  return (
    <AppShell title="Company Profile" subtitle={profileLoading ? 'Loading...' : 'Complete your company profile to prefill employee cases.'}>
      <Card padding="lg">
        {contextError && (
          <Alert variant="error" className="mb-4">{contextError}</Alert>
        )}
        {!profileLoading && !contextError && company == null && (
          <Alert variant="info" className="mb-4">
            No company record was loaded. If an admin has already assigned you to a company, try refreshing the page.
            Otherwise, fill in the form and save to create your company profile.
          </Alert>
        )}
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
