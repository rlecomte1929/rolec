(function() {
// Pathway v2 — atoms + small components.
// Inline implementations of Button / Card / Badge / ProgressBar / OptionChip / LockBadge / Icon.

const { useState, useEffect, useRef } = React;

// ─── Icon (inline lucide-style SVGs) ───
function Ico({ name, size = 16, strokeWidth = 1.75, className = '' }) {
  const p = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'currentColor', strokeWidth, strokeLinecap: 'round', strokeLinejoin: 'round', className };
  switch (name) {
    case 'arrow-right':  return <svg {...p}><path d="M5 12h14M13 5l7 7-7 7"/></svg>;
    case 'arrow-left':   return <svg {...p}><path d="M19 12H5M11 5l-7 7 7 7"/></svg>;
    case 'check':        return <svg {...p}><path d="M20 6 9 17l-5-5"/></svg>;
    case 'x':            return <svg {...p}><path d="M18 6 6 18M6 6l12 12"/></svg>;
    case 'lock':         return <svg {...p}><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>;
    case 'clock':        return <svg {...p}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>;
    case 'info':         return <svg {...p}><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></svg>;
    case 'chevron-down': return <svg {...p}><path d="m6 9 6 6 6-6"/></svg>;
    case 'chevron-right':return <svg {...p}><path d="m9 6 6 6-6 6"/></svg>;
    case 'plus':         return <svg {...p}><path d="M12 5v14M5 12h14"/></svg>;
    case 'message':      return <svg {...p}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>;
    case 'upload':       return <svg {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>;
    case 'send':         return <svg {...p}><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></svg>;
    case 'building':     return <svg {...p}><rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h.01M15 7h.01M9 11h.01M15 11h.01M9 15h.01M15 15h.01M10 21v-4h4v4"/></svg>;
    case 'pin':          return <svg {...p}><path d="M12 22s8-7.5 8-13a8 8 0 1 0-16 0c0 5.5 8 13 8 13z"/><circle cx="12" cy="9" r="2.5"/></svg>;
    case 'user':         return <svg {...p}><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>;
    case 'euro':         return <svg {...p}><path d="M18 6.5a8 8 0 1 0 0 11M3 10h12M3 14h11"/></svg>;
    case 'play':         return <svg {...p}><polygon points="6 4 20 12 6 20 6 4" fill="currentColor"/></svg>;
    case 'pause-circle': return <svg {...p}><circle cx="12" cy="12" r="9"/><path d="M10 9v6M14 9v6"/></svg>;
    case 'shield-check': return <svg {...p}><path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/></svg>;
    case 'file-text':    return <svg {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h6"/></svg>;
    default:             return <svg {...p}><circle cx="12" cy="12" r="3"/></svg>;
  }
}

// ─── Button ───
function Btn({ variant = 'primary', size = 'md', full = false, children, onClick, disabled, type, ariaLabel }) {
  return (
    <button type={type || 'button'} aria-label={ariaLabel} disabled={disabled} onClick={onClick}
      className={`btn ${size} ${variant}${full ? ' btn-full' : ''}`}>
      {children}
    </button>
  );
}

// ─── Card ───
function Crd({ pad = 'md', clickable = false, className = '', children, onClick, style }) {
  return (
    <div className={`card p-${pad}${clickable ? ' clickable' : ''}${className ? ' ' + className : ''}`}
         onClick={onClick} style={style}>
      {children}
    </div>
  );
}

// ─── Badge ───
function Pill({ variant = 'neutral', dot = false, children, className = '' }) {
  return <span className={`badge ${variant}${dot ? ' dot' : ''}${className ? ' ' + className : ''}`}>{children}</span>;
}

// ─── Progress bar ───
function Prog({ value, max = 100 }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return <div className="pbar"><div style={{ width: `${pct}%` }} /></div>;
}

// ─── Option chip ───
function Chip({ label, selected, locked, onClick, badge }) {
  return (
    <button className={`chip${selected ? ' selected' : ''}${locked ? ' locked' : ''}`}
            onClick={locked ? undefined : onClick} disabled={locked}>
      <span>{label}</span>
      {locked && badge}
      {selected && !locked && <Ico name="check" size={16} className="chip-check" />}
    </button>
  );
}

// ─── Lock badge ───
function LockBadge() {
  return <span className="lock-badge"><Ico name="lock" size={11}/> Set by HR</span>;
}

// Export to window so other JSX scripts can pick them up
Object.assign(window, {
  PV2_Ico: Ico,
  PV2_Btn: Btn,
  PV2_Crd: Crd,
  PV2_Pill: Pill,
  PV2_Prog: Prog,
  PV2_Chip: Chip,
  PV2_LockBadge: LockBadge,
});

})();
