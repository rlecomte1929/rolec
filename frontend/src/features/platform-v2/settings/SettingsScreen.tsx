/**
 * T16 — HR Profile & Settings (S7p) /settings
 * Two-tab layout: Profile | Notifications
 */

import { useRef, useState } from 'react';
import type * as React from 'react';
import { Fingerprint } from 'lucide-react';
import { FileInput } from '../../../components/antigravity/FileInput';
import { Button } from '../../../components/antigravity/Button';
import { Input } from '../../../components/antigravity/Input';
import { Avatar, Pill } from '../shared';
import { useAuth } from '../../../hooks/useAuth';
import type { UserRole } from '../../../types/relopass-api-contracts';

// ─── Passkey (AIQ-1491) ──────────────────────────────────────────────────────
// Register a passkey (Face ID / Touch ID / Windows Hello / security key) for the
// signed-in user. Additive; requires WebAuthn enabled on the Supabase project.
function PasskeySection() {
  const { registerPasskey } = useAuth();
  const [status, setStatus] = useState<'idle' | 'working' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState('');

  async function handleRegister() {
    setStatus('working');
    setMessage('');
    try {
      await registerPasskey();
      setStatus('done');
    } catch (err) {
      setStatus('error');
      setMessage((err as { message?: string })?.message ?? 'Could not register a passkey.');
    }
  }

  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '16px 20px', marginTop: '20px', maxWidth: '600px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
        <Fingerprint style={{ width: 16, height: 16 }} /> Passkey
      </div>
      <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '6px 0 12px' }}>
        Add a passkey to sign in with Face ID, Touch ID, Windows Hello, or a security key — no password needed.
      </p>
      <Button unstyled type="button" onClick={() => void handleRegister()} disabled={status === 'working'}
        style={{ padding: '9px 20px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text-primary)', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}>
        {status === 'working' ? 'Registering…' : status === 'done' ? '✓ Passkey added' : 'Register a passkey'}
      </Button>
      {status === 'error' && <p style={{ fontSize: '12px', color: 'var(--danger, #b91c1c)', marginTop: '8px' }}>{message}</p>}
    </div>
  );
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ProfileData {
  full_name: string;
  email: string;
  role: UserRole;
  company_name: string;
  phone: string;
  bio: string;
  avatar_url: string | null;
  /** Parker-I: opt-in BCP-47 target language for auto-translated journey content. '' = off. */
  preferred_language: string;
}

export type NotificationType =
  | 'new_case_assigned'
  | 'document_approved'
  | 'exception_decision'
  | 'step_blocked'
  | 'weekly_digest';

export interface NotificationPref {
  type: NotificationType;
  label: string;
  description: string;
  email: boolean;
  in_app: boolean;
}

export interface SettingsScreenProps {
  profile?: ProfileData;
  notifications?: NotificationPref[];
  onSaveProfile?: (data: ProfileData) => void;
  onSaveNotifications?: (prefs: NotificationPref[]) => void;
}

// ─── Mock ─────────────────────────────────────────────────────────────────────

const DEFAULT_PROFILE: ProfileData = {
  full_name: 'Sophie Leconte',
  email: 'sophie.leconte@company.com',
  role: 'hr',
  company_name: 'Acme Corp',
  phone: '+33 6 00 00 00 00',
  bio: 'HR specialist with 8 years of experience in global mobility and relocation programmes.',
  avatar_url: null,
  preferred_language: '',
};

// Parker-I: opt-in languages for auto-translated journey content (BCP-47).
const PREFERRED_LANGUAGE_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Off (show original)' },
  { value: 'en', label: 'English' },
  { value: 'de', label: 'German' },
  { value: 'fr', label: 'French' },
  { value: 'es', label: 'Spanish' },
  { value: 'it', label: 'Italian' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'nl', label: 'Dutch' },
  { value: 'pl', label: 'Polish' },
];

const DEFAULT_NOTIFS: NotificationPref[] = [
  { type: 'new_case_assigned', label: 'New case assigned', description: 'When a relocation case is assigned to you.', email: true, in_app: true },
  { type: 'document_approved', label: 'Document approved', description: 'When a document you reviewed is approved.', email: false, in_app: true },
  { type: 'exception_decision', label: 'Exception decision', description: 'When a policy exception request is resolved.', email: true, in_app: true },
  { type: 'step_blocked', label: 'Step blocked', description: 'When a roadmap step becomes blocked.', email: true, in_app: false },
  { type: 'weekly_digest', label: 'Weekly digest', description: 'A summary of all your active cases every Monday.', email: true, in_app: false },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

const ROLE_LABEL: Record<UserRole, string> = {
  employee: 'Employee',
  hr: 'HR',
  admin: 'Admin',
  vendor_contact: 'Vendor',
};

// ─── Toggle ───────────────────────────────────────────────────────────────────

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <Button unstyled
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      style={{
        width: '40px',
        height: '22px',
        borderRadius: '11px',
        border: 'none',
        background: checked ? 'var(--accent)' : 'var(--surface-3)',
        position: 'relative',
        cursor: 'pointer',
        transition: 'background 0.2s',
        flexShrink: 0,
      }}
    >
      <span style={{
        position: 'absolute',
        top: '3px',
        left: checked ? '21px' : '3px',
        width: '16px',
        height: '16px',
        borderRadius: '50%',
        background: '#fff',
        transition: 'left 0.2s',
        boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
      }} />
    </Button>
  );
}

// ─── Profile Tab ──────────────────────────────────────────────────────────────

interface ProfileTabProps {
  profile: ProfileData;
  onSave: (data: ProfileData) => void;
}

function ProfileTab({ profile: initial, onSave }: ProfileTabProps) {
  const [form, setForm] = useState<ProfileData>(initial);
  const fileRef = useRef<HTMLInputElement>(null);
  const [saved, setSaved] = useState(false);

  function set(key: keyof ProfileData, value: string) {
    setForm(f => ({ ...f, [key]: value }));
  }

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    onSave(form);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  const inputStyle: React.CSSProperties = {
    padding: '9px 12px',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--border)',
    background: 'var(--surface)',
    color: 'var(--text)',
    fontSize: '14px',
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box',
  };

  function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
        <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</label>
        {children}
      </div>
    );
  }

  return (
    <form onSubmit={handleSave} style={{ maxWidth: '560px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Avatar */}
      <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
        <div
          onClick={() => fileRef.current?.click()}
          onKeyDown={(e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileRef.current?.click(); } }}
          role="button"
          tabIndex={0}
          style={{ cursor: 'pointer', position: 'relative' }}
          title="Click to upload avatar"
          aria-label="Upload avatar"
        >
          <Avatar name={form.full_name} src={form.avatar_url ?? undefined} size={72} />
          <div style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            background: 'rgba(0,0,0,0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: 0,
            transition: 'opacity 0.15s',
          }}
            onMouseEnter={e => (e.currentTarget as HTMLElement).style.opacity = '1'}
            onMouseLeave={e => (e.currentTarget as HTMLElement).style.opacity = '0'}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" /></svg>
          </div>
        </div>
        <div>
          <p style={{ margin: '0 0 4px', fontSize: '15px', fontWeight: 700, color: 'var(--text)' }}>{form.full_name}</p>
          <Pill variant="info" size="sm">{ROLE_LABEL[form.role]}</Pill>
        </div>
        <FileInput ref={fileRef} accept="image/*" style={{ display: 'none' }} onChange={e => {
          const f = e.target.files?.[0];
          if (f) set('avatar_url', URL.createObjectURL(f));
        }} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <Field label="Full name">
          <Input unstyled style={inputStyle} value={form.full_name} onChange={v => set('full_name', v)} required />
        </Field>
        <Field label="Email">
          <Input unstyled style={{ ...inputStyle, background: 'var(--surface-2)', color: 'var(--text-muted)' }} value={form.email} readOnly />
        </Field>
        <Field label="Company">
          <Input unstyled style={inputStyle} value={form.company_name} onChange={v => set('company_name', v)} />
        </Field>
        <Field label="Phone">
          <Input unstyled style={inputStyle} type="tel" value={form.phone} onChange={v => set('phone', v)} />
        </Field>
        <Field label="Preferred language">
          <select
            style={inputStyle}
            value={form.preferred_language}
            onChange={e => set('preferred_language', e.target.value)}
          >
            {PREFERRED_LANGUAGE_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </Field>
      </div>

      <Field label="Bio">
        <textarea
          style={{ ...inputStyle, resize: 'vertical', minHeight: '80px', lineHeight: 1.5 }}
          value={form.bio}
          onChange={e => set('bio', e.target.value)}
          rows={3}
        />
      </Field>

      <div>
        <Button unstyled
          type="submit"
          style={{ padding: '9px 20px', borderRadius: 'var(--radius-md)', border: 'none', background: saved ? 'var(--success)' : 'var(--accent)', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer', transition: 'background 0.2s' }}
        >
          {saved ? '✓ Saved' : 'Save changes'}
        </Button>
      </div>

      {/* [AIQ-1491] Passkey registration — additive, type="button" so it never submits the form. */}
      <PasskeySection />
    </form>
  );
}

// ─── Notifications Tab ────────────────────────────────────────────────────────

interface NotificationsTabProps {
  prefs: NotificationPref[];
  onSave: (prefs: NotificationPref[]) => void;
}

function NotificationsTab({ prefs: initial, onSave }: NotificationsTabProps) {
  const [prefs, setPrefs] = useState<NotificationPref[]>(initial);
  const [saved, setSaved] = useState(false);

  function toggle(type: NotificationType, channel: 'email' | 'in_app', value: boolean) {
    setPrefs(prev => prev.map(p => p.type === type ? { ...p, [channel]: value } : p));
  }

  function handleSave() {
    onSave(prefs);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <div style={{ maxWidth: '600px' }}>
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', marginBottom: '20px' }}>
        {/* Header row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px 80px', gap: '12px', padding: '10px 20px', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
          <span>Notification</span>
          <span style={{ textAlign: 'center' }}>Email</span>
          <span style={{ textAlign: 'center' }}>In-app</span>
        </div>
        {prefs.map((pref, i) => (
          <div
            key={pref.type}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 80px 80px',
              gap: '12px',
              padding: '14px 20px',
              borderBottom: i < prefs.length - 1 ? '1px solid var(--border)' : 'none',
              alignItems: 'center',
            }}
          >
            <div>
              <p style={{ margin: '0 0 3px', fontSize: '14px', fontWeight: 600, color: 'var(--text)' }}>{pref.label}</p>
              <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>{pref.description}</p>
            </div>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <Toggle checked={pref.email} onChange={v => toggle(pref.type, 'email', v)} label={`${pref.label} email`} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <Toggle checked={pref.in_app} onChange={v => toggle(pref.type, 'in_app', v)} label={`${pref.label} in-app`} />
            </div>
          </div>
        ))}
      </div>
      <Button unstyled
        onClick={handleSave}
        style={{ padding: '9px 20px', borderRadius: 'var(--radius-md)', border: 'none', background: saved ? 'var(--success)' : 'var(--accent)', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer', transition: 'background 0.2s' }}
      >
        {saved ? '✓ Saved' : 'Save preferences'}
      </Button>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function SettingsScreen({
  profile = DEFAULT_PROFILE,
  notifications = DEFAULT_NOTIFS,
  onSaveProfile,
  onSaveNotifications,
}: SettingsScreenProps) {
  const [tab, setTab] = useState<'profile' | 'notifications'>('profile');

  const tabBtn = (id: 'profile' | 'notifications', label: string) => (
    <Button unstyled
      key={id}
      onClick={() => setTab(id)}
      style={{
        padding: '8px 18px',
        borderRadius: 'var(--radius-md)',
        border: 'none',
        background: tab === id ? 'var(--accent-soft)' : 'none',
        color: tab === id ? 'var(--accent)' : 'var(--text-secondary)',
        fontWeight: tab === id ? 700 : 400,
        fontSize: '14px',
        cursor: 'pointer',
      }}
    >
      {label}
    </Button>
  );

  return (
    <div style={{ padding: '28px 32px', maxWidth: '760px' }}>
      <h1 style={{ margin: '0 0 20px', fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>Settings</h1>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '28px', borderBottom: '1px solid var(--border)', paddingBottom: '0' }}>
        {tabBtn('profile', 'Profile')}
        {tabBtn('notifications', 'Notifications')}
      </div>

      {tab === 'profile' && (
        <ProfileTab profile={profile} onSave={data => onSaveProfile?.(data)} />
      )}
      {tab === 'notifications' && (
        <NotificationsTab prefs={notifications} onSave={prefs => onSaveNotifications?.(prefs)} />
      )}
    </div>
  );
}
