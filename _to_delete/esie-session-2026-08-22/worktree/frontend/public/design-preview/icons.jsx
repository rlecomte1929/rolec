// Inline SVG icons — minimal lucide-style set
const Icon = ({ name, size = 18, className = '', strokeWidth = 1.75 }) => {
  const props = {
    width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'currentColor', strokeWidth, strokeLinecap: 'round', strokeLinejoin: 'round',
    className,
  };
  switch (name) {
    case 'arrow-right': return <svg {...props}><path d="M5 12h14M13 5l7 7-7 7"/></svg>;
    case 'arrow-left':  return <svg {...props}><path d="M19 12H5M11 5l-7 7 7 7"/></svg>;
    case 'check':       return <svg {...props}><path d="M20 6 9 17l-5-5"/></svg>;
    case 'check-circle':return <svg {...props}><circle cx="12" cy="12" r="10"/><path d="m8 12 3 3 5-6"/></svg>;
    case 'lock':        return <svg {...props}><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>;
    case 'clock':       return <svg {...props}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>;
    case 'dot':         return <svg {...props}><circle cx="12" cy="12" r="4" fill="currentColor"/></svg>;
    case 'play':        return <svg {...props}><circle cx="12" cy="12" r="9"/><path d="M10 8.5v7l6-3.5z" fill="currentColor"/></svg>;
    case 'edit':        return <svg {...props}><path d="M11 4H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-6"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z"/></svg>;
    case 'sparkle':     return <svg {...props}><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z"/><path d="M19 14l.7 2 2 .7-2 .7L19 19l-.7-1.6-2-.7 2-.7z"/></svg>;
    case 'info':        return <svg {...props}><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></svg>;
    case 'plane':       return <svg {...props}><path d="M10.5 13.5 2 11l8.5-2L13 2l3 7 6 1-6 4-2 6z"/></svg>;
    case 'globe':       return <svg {...props}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a13 13 0 0 1 0 18M12 3a13 13 0 0 0 0 18"/></svg>;
    case 'home':        return <svg {...props}><path d="M3 11l9-8 9 8v9a2 2 0 0 1-2 2h-4v-7H9v7H5a2 2 0 0 1-2-2z"/></svg>;
    case 'briefcase':   return <svg {...props}><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M2 13h20"/></svg>;
    case 'book':        return <svg {...props}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5V22h16"/></svg>;
    case 'heart':       return <svg {...props}><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>;
    case 'trending':    return <svg {...props}><path d="m3 17 6-6 4 4 7-7M14 8h7v7"/></svg>;
    case 'sun':         return <svg {...props}><circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4"/></svg>;
    case 'shield':      return <svg {...props}><path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6z"/></svg>;
    case 'user':        return <svg {...props}><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>;
    case 'users':       return <svg {...props}><circle cx="9" cy="8" r="3.5"/><circle cx="17" cy="9" r="3"/><path d="M2 21a7 7 0 0 1 14 0M14 21a6 6 0 0 1 8-4.5"/></svg>;
    case 'family':      return <svg {...props}><circle cx="7" cy="8" r="2.5"/><circle cx="17" cy="8" r="2.5"/><circle cx="12" cy="17" r="1.5"/><path d="M3 18a4 4 0 0 1 8 0M13 18a4 4 0 0 1 8 0M11 17h2"/></svg>;
    case 'baby':        return <svg {...props}><circle cx="12" cy="8" r="3.5"/><path d="M5 21a7 7 0 0 1 14 0M9 8.5h.01M15 8.5h.01M10 11s.5 1 2 1 2-1 2-1"/></svg>;
    case 'handshake':   return <svg {...props}><path d="M11 17l-4-4-3 3 4 4zM13 17l3 3 4-4-3-3M7 13l5-5 4 4M3 12l4-4M21 12l-4-4"/></svg>;
    case 'search':      return <svg {...props}><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>;
    case 'fast':        return <svg {...props}><path d="m13 2-11 14h9l-1 8 11-14h-9z"/></svg>;
    case 'mid':         return <svg {...props}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>;
    case 'slow':        return <svg {...props}><rect x="6" y="2" width="12" height="20" rx="2"/><path d="M9 14a3 3 0 1 1 6 0c0 1.5-3 2-3 4M9 7l6 1"/></svg>;
    case 'flex':        return <svg {...props}><path d="M3 12h4l2-6 4 12 2-6h6"/></svg>;
    case 'building':    return <svg {...props}><rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h.01M15 7h.01M9 11h.01M15 11h.01M9 15h.01M15 15h.01M10 21v-4h4v4"/></svg>;
    case 'lawyer':      return <svg {...props}><path d="M12 3v18M5 7h14M7 7l-3 7h6zM17 7l-3 7h6zM4 14a3 3 0 0 0 6 0M14 14a3 3 0 0 0 6 0"/></svg>;
    case 'map':         return <svg {...props}><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/></svg>;
    case 'pin':         return <svg {...props}><path d="M12 22s8-7.5 8-13a8 8 0 1 0-16 0c0 5.5 8 13 8 13z"/><circle cx="12" cy="9" r="2.5"/></svg>;
    case 'chevron-down':return <svg {...props}><path d="m6 9 6 6 6-6"/></svg>;
    case 'chevron-right':return <svg {...props}><path d="m9 6 6 6-6 6"/></svg>;
    case 'message':     return <svg {...props}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>;
    case 'route':       return <svg {...props}><circle cx="6" cy="19" r="2.5"/><circle cx="18" cy="5" r="2.5"/><path d="M8.5 18.5C14 18 18 14 18 8"/></svg>;
    case 'compass':     return <svg {...props}><circle cx="12" cy="12" r="9"/><path d="m16 8-3 6-6 3 3-6z"/></svg>;
    default: return <svg {...props}><circle cx="12" cy="12" r="3"/></svg>;
  }
};

window.Icon = Icon;
