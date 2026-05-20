import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

type PreviewEntry = {
  key: string;
  label: string;
  file: string;
  hint: string;
  primary?: boolean;
};

const PROTOTYPES: PreviewEntry[] = [
  {
    key: 'platform',
    label: 'ReloPass Platform',
    file: 'ReloPass Platform.html',
    hint: 'Full platform shell — auth, intake, HR, admin, policy builder, exceptions (25+ screens)',
    primary: true,
  },
  {
    key: 'pathway-final',
    label: 'Pathway — Final',
    file: 'Pathway Final.html',
    hint: 'Latest single-page intake / journey design',
  },
  {
    key: 'pathway-v2',
    label: 'Pathway — v2',
    file: 'Pathway v2.html',
    hint: 'Iteration with separated timeline / intake / header atoms',
  },
  {
    key: 'pathway-simple',
    label: 'Pathway — Simple',
    file: 'Pathway Simple.html',
    hint: 'Original simpler pathway prototype',
  },
];

const BASE = '/design-preview';

export function DesignPreview() {
  const [params, setParams] = useSearchParams();
  const requested = params.get('p') ?? 'platform';
  const selected = useMemo(
    () => PROTOTYPES.find((p) => p.key === requested) ?? PROTOTYPES[0],
    [requested],
  );
  const [chromeHidden, setChromeHidden] = useState(false);

  useEffect(() => {
    document.title = `Design preview — ${selected.label}`;
  }, [selected.label]);

  const src = `${BASE}/${encodeURIComponent(selected.file)}`;

  if (chromeHidden) {
    return (
      <div style={{ position: 'fixed', inset: 0, background: '#000' }}>
        <iframe
          key={selected.key}
          src={src}
          title={selected.label}
          style={{ width: '100%', height: '100%', border: 'none' }}
        />
        <button
          type="button"
          onClick={() => setChromeHidden(false)}
          style={{
            position: 'fixed',
            top: 8,
            right: 8,
            zIndex: 10,
            padding: '6px 12px',
            fontSize: 12,
            borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.4)',
            background: 'rgba(0,0,0,0.7)',
            color: 'white',
            cursor: 'pointer',
          }}
        >
          Show chrome
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#f8fafc' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          padding: '10px 16px',
          borderBottom: '1px solid #e5e7eb',
          background: 'white',
          flexShrink: 0,
        }}
      >
        <strong style={{ fontSize: 14 }}>Design preview</strong>
        <span
          style={{
            fontSize: 11,
            padding: '2px 8px',
            background: '#fef3c7',
            color: '#78350f',
            borderRadius: 999,
            border: '1px solid #fde68a',
          }}
        >
          sandbox · static · mock data only
        </span>
        <select
          value={selected.key}
          onChange={(e) => setParams({ p: e.target.value })}
          style={{
            marginLeft: 'auto',
            fontSize: 13,
            padding: '6px 10px',
            borderRadius: 6,
            border: '1px solid #d1d5db',
            background: 'white',
          }}
        >
          {PROTOTYPES.map((p) => (
            <option key={p.key} value={p.key}>
              {p.label}
              {p.primary ? ' (primary)' : ''}
            </option>
          ))}
        </select>
        <a
          href={src}
          target="_blank"
          rel="noreferrer"
          style={{ fontSize: 12, color: '#4f46e5', textDecoration: 'none' }}
        >
          Open in new tab ↗
        </a>
        <button
          type="button"
          onClick={() => setChromeHidden(true)}
          style={{
            fontSize: 12,
            padding: '6px 10px',
            borderRadius: 6,
            border: '1px solid #d1d5db',
            background: 'white',
            cursor: 'pointer',
          }}
        >
          Fullscreen
        </button>
      </header>
      <p
        style={{
          margin: 0,
          padding: '6px 16px',
          fontSize: 12,
          color: '#6b7280',
          borderBottom: '1px solid #f1f5f9',
          background: '#fafafa',
        }}
      >
        {selected.hint}. Use the floating <em>Tweaks</em> panel inside the prototype to switch screens, roles, demo
        data, and theme.
      </p>
      <iframe
        key={selected.key}
        src={src}
        title={selected.label}
        style={{ flex: 1, width: '100%', border: 'none', background: 'white' }}
      />
    </div>
  );
}

export default DesignPreview;
