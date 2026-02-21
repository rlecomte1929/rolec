import React, { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Card, Button, Input, Alert } from '../components/antigravity';
import { hrAPI } from '../api/client';
import { useNavigate } from 'react-router-dom';
import { safeNavigate } from '../navigation/safeNavigate';

export const HrCompanyProfile: React.FC = () => {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [country, setCountry] = useState('');
  const [sizeBand, setSizeBand] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [hrContact, setHrContact] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    hrAPI.getCompanyProfile()
      .then((res) => {
        if (res.company) {
          setName(res.company.name || '');
          setCountry(res.company.country || '');
          setSizeBand(res.company.size_band || '');
          setAddress(res.company.address || '');
          setPhone(res.company.phone || '');
          setHrContact(res.company.hr_contact || '');
        }
      })
      .catch((err: any) => {
        if (err?.response?.status === 401) safeNavigate(navigate, 'landing');
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  const save = async () => {
    if (!name.trim()) {
      setError('Company name is required.');
      return;
    }
    setError('');
    setSaving(true);
    try {
      await hrAPI.saveCompanyProfile({
        name: name.trim(),
        country: country.trim(),
        size_band: sizeBand.trim(),
        address: address.trim(),
        phone: phone.trim(),
        hr_contact: hrContact.trim(),
      });
      safeNavigate(navigate, 'hrDashboard');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save company profile.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <AppShell title="Company Profile" subtitle="Set up your organization">
        <div className="text-sm text-[#6b7280] py-8">Loading company profile...</div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Company Profile" subtitle="Complete your company profile to prefill employee cases.">
      <Card padding="lg">
        {error && <Alert variant="error" className="mb-4">{error}</Alert>}
        <div className="space-y-4">
          <Input label="Company name" value={name} onChange={setName} fullWidth />
          <Input label="Country" value={country} onChange={setCountry} fullWidth />
          <Input label="Company size band" value={sizeBand} onChange={setSizeBand} placeholder="e.g. 50-200" fullWidth />
          <Input label="Address" value={address} onChange={setAddress} fullWidth />
          <Input label="Phone" value={phone} onChange={setPhone} fullWidth />
          <Input label="HR contact" value={hrContact} onChange={setHrContact} placeholder="e.g. hr@company.com" fullWidth />
          <Button onClick={save} disabled={saving}>
            {saving ? 'Saving...' : 'Save company profile'}
          </Button>
        </div>
      </Card>
    </AppShell>
  );
};
