/**
 * T16 — HR Profile & Settings (S7p) /settings
 * Two-tab layout: Profile | Notifications
 */

import { useRef, useState } from 'react';
import { Avatar, Pill } from '../shared';
import type { UserRole } from '../../../types/relopass-api-contracts';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ProfileData {
  full_name: string;
  email: string;
  role: UserRole;
  company_name: string;
  phone: string;
  bio: string;
  avatar_url: string | null;
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
};

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
    <button
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
    </button>
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
          style={{ cursor: 'pointer', position: 'relative' }}
          title="Click to upload avatar"
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
        <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={e => {
          const f = e.target.files?.[0];
          if (f) set('avatar_url', URL.createObjectURL(f));
        }} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <Field label="Full name">
          <input style={inputStyle} value={form.full_name} onChange={e => set('full_name', e.target.value)} required />
        </Field>
        <Field label="Email">
          <input style={{ ...inputStyle, background: 'var(--surface-2)', color: 'var(--text-muted)' }} value={form.email} readOnly />
        </Field>
        <Field label="Company">
          <input style={inputStyle} value={form.company_name} onChange={e => set('company_name', e.target.value)} />
        </Field>
        <Field label="Phone">
          <input style={inputStyle} type="tel" value={form.phone} onChange={e => set('phone', e.target.value)} />
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
        <button
          type="submit"
          style={{ padding: '9px 20px', borderRadius: 'var(--radius-md)', border: 'none', background: saved ? 'var(--success)' : 'var(--accent)', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer', transition: 'background 0.2s' }}
        >
          {saved ? '✓ Saved' : 'Save changes'}
        </button>
      </div>
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
      <button
        onClick={handleSave}
        style={{ padding: '9px 20px', borderRadius: 'var(--radius-md)', border: 'none', background: saved ? 'var(--success)' : 'var(--accent)', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer', transition: 'background 0.2s' }}
      >
        {saved ? '✓ Saved' : 'Save preferences'}
      </button>
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
    <button
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
    </button>
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
