// platform-s0-auth.jsx — Sign-in / Create-account with animated globe panel
(function() {
const { useState, useEffect, useRef } = React;

// Persona registry (auth response simulation)
const PERSONAS = {
  admin:    { role: 'ADMIN',    name: 'Romain Aubertin',  email: 'romain@relopass.com',           avatar: 'RA', route: 's9',  routeLabel: '/admin',               sidebarRole: 'admin' },
  hr:       { role: 'HR',       name: 'Helena Müller',     email: 'helena.muller@aurora-energy.com', avatar: 'HM', route: 's7',  routeLabel: '/hr/dashboard',     sidebarRole: 'hr' },
  employee: { role: 'EMPLOYEE', name: 'Marc Bouchard',     email: 'marc.bouchard@aurora-energy.com', avatar: 'MB', route: 's3',  routeLabel: '/employee/dashboard', sidebarRole: 'standard' },
};

// ── Animated Globe Canvas ─────────────────────────────────────────
function GlobeCanvas() {
  const ref = useRef(null);
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext('2d');

    let rafId;
    const resize = () => {
      cv.width = cv.clientWidth || 900;
      cv.height = cv.clientHeight || 900;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(cv.parentElement);

    const G = () => {
      const W = cv.width, H = cv.height;
      const R = Math.min(W * 0.44, H * 0.42);
      return { W, H, X: W * 0.52, Y: H * 0.50, RX: R, RY: R * 1.02 };
    };
    const proj = (lat, lon, g) => [
      g.X + g.RX * (lon / 90),
      g.Y - g.RY * ((lat - 15) / 72),
    ];

    const CITIES = [
      { key: 'paris', lat: 48.9, lon: 2.3, code: 'FR' },
      { key: 'oslo', lat: 59.9, lon: 10.7, code: 'NO' },
      { key: 'london', lat: 51.5, lon: -0.1, code: 'GB' },
      { key: 'dubai', lat: 25.2, lon: 55.3, code: 'AE' },
      { key: 'singapore', lat: 1.3, lon: 103.8, code: 'SG' },
      { key: 'newyork', lat: 40.7, lon: -74.0, code: 'US' },
      { key: 'toronto', lat: 43.7, lon: -79.4, code: 'CA' },
      { key: 'saopaulo', lat: -23.5, lon: -46.6, code: 'BR' },
      { key: 'berlin', lat: 52.5, lon: 13.4, code: 'DE' },
      { key: 'sydney', lat: -33.9, lon: 151.2, code: 'AU' },
    ];
    const cityMap = Object.fromEntries(CITIES.map(c => [c.key, c]));
    const CORR_DEF = [
      { f: 'paris', t: 'oslo', col: '#1DBFA2', lbl: 'FR → NO', delay: 0 },
      { f: 'london', t: 'dubai', col: '#4A9AE8', lbl: 'GB → AE', delay: 55 },
      { f: 'newyork', t: 'london', col: '#EFA827', lbl: 'US → GB', delay: 110 },
      { f: 'toronto', t: 'berlin', col: '#1DBFA2', lbl: 'CA → DE', delay: 25 },
      { f: 'dubai', t: 'singapore', col: '#4A9AE8', lbl: 'AE → SG', delay: 148 },
      { f: 'saopaulo', t: 'london', col: '#EFA827', lbl: 'BR → GB', delay: 80 },
      { f: 'berlin', t: 'dubai', col: '#1DBFA2', lbl: 'DE → AE', delay: 170 },
    ];
    const corrs = CORR_DEF.map(d => ({ ...d, phase: 'idle', prog: 0, opa: 0, timer: d.delay, lblAmt: 0 }));
    const pulses = [];

    const CONTS = [
      [[70,20],[65,-5],[55,-10],[46,-8],[36,10],[38,36],[56,40],[70,28]],
      [[37,-5],[37,50],[15,50],[-2,42],[-35,26],[-22,-17],[14,-18],[37,-5]],
      [[70,37],[70,142],[55,142],[24,121],[10,104],[5,100],[10,44],[40,37],[70,37]],
      [[70,-142],[70,-56],[50,-57],[30,-82],[20,-90],[20,-118],[50,-130],[70,-142]],
      [[10,-80],[8,-62],[-5,-35],[-33,-52],[-55,-68],[-40,-73],[0,-80],[10,-80]],
      [[-12,114],[-12,154],[-42,148],[-40,114],[-12,114]],
    ];
    const cpOf = (fx, fy, tx, ty) => {
      const d = Math.hypot(tx - fx, ty - fy);
      return [(fx + tx) / 2, (fy + ty) / 2 - d * 0.32];
    };
    const bez = (fx, fy, cx, cy, tx, ty, t) => {
      const u = 1 - t;
      return [u*u*fx + 2*u*t*cx + t*t*tx, u*u*fy + 2*u*t*cy + t*t*ty];
    };
    const h2 = (v) => Math.max(0, Math.min(255, Math.round(v * 255))).toString(16).padStart(2, '0');

    const drawBg = (g) => {
      ctx.fillStyle = '#0d1f3a';
      ctx.fillRect(0, 0, g.W, g.H);
      const gr = ctx.createRadialGradient(g.X, g.Y * 0.7, 0, g.X, g.Y, g.RX * 1.4);
      gr.addColorStop(0, 'rgba(20,60,150,0.18)');
      gr.addColorStop(1, 'rgba(13,31,58,0)');
      ctx.fillStyle = gr;
      ctx.fillRect(0, 0, g.W, g.H);
    };
    const drawContinents = (g) => {
      CONTS.forEach(pts => {
        ctx.beginPath();
        pts.forEach(([lat, lon], i) => {
          const [x, y] = proj(lat, lon, g);
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        ctx.closePath();
        ctx.fillStyle = 'rgba(30,70,170,0.065)'; ctx.fill();
        ctx.strokeStyle = 'rgba(40,90,200,0.12)';
        ctx.lineWidth = 0.5; ctx.stroke();
      });
    };
    const drawGlobe = (g) => {
      for (let lat = -60; lat <= 70; lat += 20) {
        const [, py] = proj(lat, 0, g);
        const cosL = Math.abs(Math.cos(lat * Math.PI / 180));
        const rx = g.RX * cosL * 0.86;
        if (rx < 6) continue;
        ctx.beginPath();
        ctx.ellipse(g.X, py, rx, g.RY * 0.10, 0, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(50,100,220,0.13)'; ctx.lineWidth = 0.65; ctx.stroke();
      }
      for (let lon = -150; lon <= 150; lon += 30) {
        const angle = (lon / 90) * (Math.PI / 2.9);
        ctx.save();
        ctx.translate(g.X, g.Y); ctx.rotate(angle);
        ctx.beginPath();
        ctx.ellipse(0, 0, g.RX * 0.28, g.RY, 0, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(50,100,220,0.13)'; ctx.lineWidth = 0.65; ctx.stroke();
        ctx.restore();
      }
      ctx.beginPath();
      ctx.ellipse(g.X, g.Y, g.RX, g.RY, 0, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(50,100,220,0.26)'; ctx.lineWidth = 1; ctx.stroke();
    };
    const updateCorrs = (g) => {
      const DF = 115, HF = 95, FF = 58;
      corrs.forEach(c => {
        if (c.phase === 'idle') {
          if (--c.timer <= 0) { c.phase = 'drawing'; c.prog = 0; c.opa = 0; }
        } else if (c.phase === 'drawing') {
          c.prog = Math.min(1, c.prog + 1 / DF);
          c.opa = Math.min(1, c.opa + 2.8 / DF);
          if (c.prog >= 1) {
            c.phase = 'visible'; c.timer = HF; c.lblAmt = 0;
            const tc = cityMap[c.t];
            if (tc) {
              const [px, py] = proj(tc.lat, tc.lon, g);
              pulses.push({ x: px, y: py, r: 5, opa: 1, col: c.col });
            }
          }
        } else if (c.phase === 'visible') {
          c.timer--;
          c.lblAmt = Math.min(HF, (HF - c.timer) * 2.8);
          if (c.timer <= 0) c.phase = 'fading';
        } else if (c.phase === 'fading') {
          c.opa = Math.max(0, c.opa - 1 / FF);
          if (c.opa <= 0) {
            c.phase = 'idle';
            c.timer = 35 + (Math.random() * 85 | 0);
            c.prog = 0; c.lblAmt = 0;
          }
        }
      });
    };
    const drawCorrs = (g) => {
      corrs.forEach(c => {
        if (c.phase === 'idle' || c.opa <= 0) return;
        const fc = cityMap[c.f], tc = cityMap[c.t];
        if (!fc || !tc) return;
        const [fx, fy] = proj(fc.lat, fc.lon, g);
        const [tx, ty] = proj(tc.lat, tc.lon, g);
        const [cpx, cpy] = cpOf(fx, fy, tx, ty);
        const steps = 50, maxS = Math.floor(c.prog * steps);
        ctx.beginPath();
        for (let i = 0; i <= maxS; i++) {
          const [px, py] = bez(fx, fy, cpx, cpy, tx, ty, i / steps);
          i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
        }
        ctx.strokeStyle = c.col + h2(c.opa * 0.82);
        ctx.lineWidth = 1.5; ctx.stroke();
        if (c.phase === 'drawing') {
          const [px, py] = bez(fx, fy, cpx, cpy, tx, ty, c.prog);
          const gr = ctx.createRadialGradient(px, py, 0, px, py, 14);
          gr.addColorStop(0, c.col + 'FF');
          gr.addColorStop(0.45, c.col + '66');
          gr.addColorStop(1, c.col + '00');
          ctx.fillStyle = gr;
          ctx.beginPath(); ctx.arc(px, py, 14, 0, Math.PI * 2); ctx.fill();
        }
        if (c.lblAmt > 0 && c.opa > 0.28) {
          const la = Math.min(1, c.lblAmt / 65) * c.opa;
          const [mx, my] = bez(fx, fy, cpx, cpy, tx, ty, 0.5);
          ctx.save();
          ctx.font = '500 10px system-ui, sans-serif';
          ctx.fillStyle = c.col + h2(la * 0.88);
          ctx.textAlign = 'center';
          ctx.fillText(c.lbl, mx, my - 11);
          ctx.restore();
        }
      });
    };
    const drawPulses = () => {
      for (let i = pulses.length - 1; i >= 0; i--) {
        const p = pulses[i];
        p.r += 2.0; p.opa -= 0.026;
        if (p.opa <= 0) { pulses.splice(i, 1); continue; }
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.strokeStyle = p.col + h2(p.opa * 0.68);
        ctx.lineWidth = 1; ctx.stroke();
      }
    };
    const drawCities = (g) => {
      CITIES.forEach(c => {
        const [x, y] = proj(c.lat, c.lon, g);
        ctx.beginPath(); ctx.arc(x, y, 6.5, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255,255,255,0.16)'; ctx.lineWidth = 1; ctx.stroke();
        ctx.beginPath(); ctx.arc(x, y, 2.8, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,255,255,0.86)'; ctx.fill();
        ctx.font = '400 9px system-ui, sans-serif';
        ctx.fillStyle = 'rgba(185,210,250,0.50)';
        ctx.textAlign = 'center';
        ctx.fillText(c.code, x, y - 12);
      });
    };
    const drawVignette = (g) => {
      const gr = ctx.createLinearGradient(g.W - 60, 0, g.W, 0);
      gr.addColorStop(0, 'rgba(13,31,58,0)');
      gr.addColorStop(1, 'rgba(13,31,58,0.70)');
      ctx.fillStyle = gr; ctx.fillRect(g.W - 60, 0, 60, g.H);
      const gb = ctx.createLinearGradient(0, g.H - 60, 0, g.H);
      gb.addColorStop(0, 'rgba(13,31,58,0)');
      gb.addColorStop(1, 'rgba(13,31,58,0.55)');
      ctx.fillStyle = gb; ctx.fillRect(0, g.H - 60, g.W, 60);
    };
    const frame = () => {
      const g = G();
      ctx.clearRect(0, 0, g.W, g.H);
      drawBg(g);
      drawContinents(g);
      drawGlobe(g);
      updateCorrs(g);
      drawCorrs(g);
      drawPulses();
      drawCities(g);
      drawVignette(g);
      rafId = requestAnimationFrame(frame);
    };
    frame();
    return () => { cancelAnimationFrame(rafId); ro.disconnect(); };
  }, []);
  return <canvas ref={ref} className="globe-canvas" aria-hidden="true"/>;
}

// ── Routing Flash ─────────────────────────────────────────────────
function RoutingFlash({ persona }) {
  return (
    <div className="routing-flash">
      <div className="routing-flash-card">
        <div className="routing-flash-avatar">{persona.avatar}</div>
        <div>
          <div className="t">Welcome back, <span className="name">{persona.name.split(' ')[0]}</span></div>
          <div className="s">Verifying session and loading your workspace…</div>
        </div>
        <div className="route">
          <span>{persona.role}</span>
          <span>→</span>
          <span>{persona.routeLabel}</span>
        </div>
      </div>
    </div>
  );
}

// ── Eye icon ──────────────────────────────────────────────────────
const EyeIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
);

// ── Main AuthScreen ───────────────────────────────────────────────
function AuthScreen({ onAuthenticated, initialMode = 'login' }) {
  const [tab, setTab] = useState(initialMode === 'register' ? 'create' : 'signin');
  useEffect(() => setTab(initialMode === 'register' ? 'create' : 'signin'), [initialMode]);

  // Sign-in
  const [signinEmail, setSigninEmail] = useState('');
  const [signinPassword, setSigninPassword] = useState('');
  const [signinShowPw, setSigninShowPw] = useState(false);
  const [signinError, setSigninError] = useState('');
  const [signinLoading, setSigninLoading] = useState(false);

  // Create
  const [createName, setCreateName] = useState('');
  const [createEmail, setCreateEmail] = useState('');
  const [createCompany, setCreateCompany] = useState('');
  const [createPassword, setCreatePassword] = useState('');
  const [createShowPw, setCreateShowPw] = useState(false);
  const [createError, setCreateError] = useState('');
  const [createLoading, setCreateLoading] = useState(false);

  const [activePersona, setActivePersona] = useState(null);

  // Reset errors on input
  useEffect(() => { if (signinError) setSigninError(''); }, [signinEmail, signinPassword]);
  useEffect(() => { if (createError) setCreateError(''); }, [createEmail, createPassword, createName]);

  const submitSignIn = (e) => {
    e?.preventDefault?.();
    if (!signinEmail || !signinPassword) {
      setSigninError('Please fill in both fields.');
      return;
    }
    setSigninLoading(true);
    setTimeout(() => {
      const key = signinEmail.trim().toLowerCase();
      let persona = null;
      if (key.endsWith('@relopass.com') || key === 'admin') persona = PERSONAS.admin;
      else if (key.includes('helena') || key.includes('hr@') || key === 'hr') persona = PERSONAS.hr;
      else if (key.includes('marc') || key.includes('@aurora') || key === 'employee' || key === 'demo') persona = PERSONAS.employee;
      if (!persona || signinPassword.length < 4) {
        setSigninError('Incorrect email or password. Try the one-click demo below.');
        setSigninLoading(false);
        return;
      }
      setActivePersona(persona);
      setTimeout(() => onAuthenticated?.(persona), 1400);
    }, 900);
  };

  const submitCreate = (e) => {
    e?.preventDefault?.();
    if (!createName || !createEmail || !createPassword) {
      setCreateError('Please fill in all required fields.');
      return;
    }
    if (createPassword.length < 8) {
      setCreateError('Password must be at least 8 characters.');
      return;
    }
    setCreateLoading(true);
    setTimeout(() => {
      const persona = { ...PERSONAS.employee, name: createName, email: createEmail };
      setActivePersona(persona);
      setTimeout(() => onAuthenticated?.(persona), 1400);
    }, 900);
  };

  const demoLogin = (key) => {
    const p = PERSONAS[key];
    setActivePersona(p);
    setTimeout(() => onAuthenticated?.(p), 1100);
  };

  return (
    <div className="auth-screen">
      {/* GLOBE PANEL */}
      <div className="globe-panel">
        <GlobeCanvas/>
        <div className="globe-logo">
          <img src="assets/relopass-mark.png" alt="ReloPass" width="26" height="26" style={{ display: 'block' }}/>
          <span className="wordmark">ReloPass</span>
          <span className="product-label">· Platform</span>
        </div>
        <div className="globe-badge">
          <span className="live-tag">• LIVE ACROSS 47 CORRIDORS</span>
          <div className="case-card">
            <div className="case-icon">↝</div>
            <div className="case-info">
              <div className="case-name">
                Marc B. · FR → NO
                <span className="case-live">LIVE</span>
              </div>
              <div className="case-meta">visa approved · 2,882 active relocations across 47 corridors</div>
            </div>
          </div>
        </div>
      </div>

      {/* FORM PANEL */}
      <div className="form-panel">
        <div className="form-inner">
          {/* Tabs */}
          <div className="tab-switcher" role="tablist">
            <button className={`tab-btn${tab === 'signin' ? ' active' : ''}`}
              role="tab" aria-selected={tab === 'signin'}
              onClick={() => setTab('signin')}>
              Sign in
            </button>
            <button className={`tab-btn${tab === 'create' ? ' active' : ''}`}
              role="tab" aria-selected={tab === 'create'}
              onClick={() => setTab('create')}>
              Create account
            </button>
          </div>

          {/* SIGN IN */}
          {tab === 'signin' && (
            <div role="tabpanel">
              <h1 className="form-heading">Sign in to ReloPass</h1>
              <p className="form-subhead">Welcome back. Pick up where you left off.</p>

              {signinError && <p className="form-error">{signinError}</p>}

              <form onSubmit={submitSignIn} noValidate>
                <div className="auth-field-new">
                  <label htmlFor="signin-email">Email or username</label>
                  <input id="signin-email" type="email" placeholder="you@company.com"
                    autoComplete="email" value={signinEmail} disabled={signinLoading}
                    onChange={(e) => setSigninEmail(e.target.value)}/>
                </div>
                <div className="auth-field-new">
                  <label htmlFor="signin-password">
                    Password
                    <a className="forgot-link" onClick={(e) => e.preventDefault()} href="#">Forgot?</a>
                  </label>
                  <div className="field-wrap">
                    <input id="signin-password" type={signinShowPw ? 'text' : 'password'}
                      placeholder="••••••••" autoComplete="current-password"
                      value={signinPassword} disabled={signinLoading}
                      onChange={(e) => setSigninPassword(e.target.value)}/>
                    <button type="button" className={`pw-toggle${signinShowPw ? ' shown' : ''}`}
                      aria-label={signinShowPw ? 'Hide password' : 'Show password'}
                      onClick={() => setSigninShowPw(s => !s)}>
                      <EyeIcon/>
                    </button>
                  </div>
                </div>
                <button type="submit" className="btn-primary" disabled={signinLoading}>
                  {signinLoading && <span className="spinner"/>}
                  <span>{signinLoading ? 'Signing in…' : 'Sign in'}</span>
                </button>
              </form>

              <div className="auth-divider"><span>or</span></div>

              <div className="sso-row">
                <button className="btn-sso">
                  <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                  Google
                </button>
                <button className="btn-sso">
                  <svg width="16" height="16" viewBox="0 0 23 23" aria-hidden="true">
                    <rect x="1" y="1" width="10" height="10" fill="#f35325"/>
                    <rect x="12" y="1" width="10" height="10" fill="#81bc06"/>
                    <rect x="1" y="12" width="10" height="10" fill="#05a6f0"/>
                    <rect x="12" y="12" width="10" height="10" fill="#ffba08"/>
                  </svg>
                  Microsoft SSO
                </button>
              </div>

              <p className="switch-link">
                New to ReloPass? <a onClick={() => setTab('create')}>Create an account →</a>
              </p>

              <div className="demo-panel">
                <div className="demo-label">
                  <span>ONE-CLICK DEMO</span>
                  <span className="proto-badge">PROTOTYPE</span>
                </div>
                <div className="demo-cards">
                  <button className="demo-card" onClick={() => demoLogin('admin')}>
                    <div className="demo-card-role">Admin</div>
                    <div className="demo-card-name">ReloPass team</div>
                    <div className="demo-card-link">→ /ADMIN</div>
                  </button>
                  <button className="demo-card" onClick={() => demoLogin('hr')}>
                    <div className="demo-card-role">HR</div>
                    <div className="demo-card-name">Helena · Aurora</div>
                    <div className="demo-card-link">→ /HR/DASHBOARD</div>
                  </button>
                  <button className="demo-card" onClick={() => demoLogin('employee')}>
                    <div className="demo-card-role">Employee</div>
                    <div className="demo-card-name">Marc · FR→NO</div>
                    <div className="demo-card-link">→ /EMPLOYEE/DASHBOARD</div>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* CREATE */}
          {tab === 'create' && (
            <div role="tabpanel">
              <h1 className="form-heading">Create your account</h1>
              <p className="form-subhead">Set up your ReloPass workspace in minutes.</p>

              {createError && <p className="form-error">{createError}</p>}

              <form onSubmit={submitCreate} noValidate>
                <div className="auth-field-new">
                  <label htmlFor="create-name">Full name</label>
                  <input id="create-name" type="text" placeholder="Jane Smith"
                    autoComplete="name" value={createName} disabled={createLoading}
                    onChange={(e) => setCreateName(e.target.value)}/>
                </div>
                <div className="auth-field-new">
                  <label htmlFor="create-email">Work email</label>
                  <input id="create-email" type="email" placeholder="you@company.com"
                    autoComplete="email" value={createEmail} disabled={createLoading}
                    onChange={(e) => setCreateEmail(e.target.value)}/>
                </div>
                <div className="auth-field-new">
                  <label htmlFor="create-company">Company</label>
                  <input id="create-company" type="text" placeholder="Acme Corp"
                    autoComplete="organization" value={createCompany} disabled={createLoading}
                    onChange={(e) => setCreateCompany(e.target.value)}/>
                </div>
                <div className="auth-field-new">
                  <label htmlFor="create-password">Password</label>
                  <div className="field-wrap">
                    <input id="create-password" type={createShowPw ? 'text' : 'password'}
                      placeholder="Min. 8 characters" autoComplete="new-password"
                      value={createPassword} disabled={createLoading}
                      onChange={(e) => setCreatePassword(e.target.value)}/>
                    <button type="button" className={`pw-toggle${createShowPw ? ' shown' : ''}`}
                      aria-label={createShowPw ? 'Hide password' : 'Show password'}
                      onClick={() => setCreateShowPw(s => !s)}>
                      <EyeIcon/>
                    </button>
                  </div>
                </div>
                <button type="submit" className="btn-primary" disabled={createLoading}>
                  {createLoading && <span className="spinner"/>}
                  <span>{createLoading ? 'Creating account…' : 'Create account'}</span>
                </button>
              </form>

              <p className="switch-link" style={{ marginTop: 20 }}>
                Already have an account? <a onClick={() => setTab('signin')}>Sign in →</a>
              </p>

              <p className="fine-print">
                By creating an account you agree to the <a href="#">Terms of Service</a> and <a href="#">Privacy Policy</a>.
              </p>
            </div>
          )}
        </div>

        <footer className="form-footer-new">
          <a href="#">Privacy</a>
          <a href="#">Terms</a>
          <a href="#">Support</a>
          <span>© 2026 ReloPass</span>
        </footer>
      </div>

      {activePersona && <RoutingFlash persona={activePersona}/>}
    </div>
  );
}

window.AuthScreen = AuthScreen;
window.AUTH_PERSONAS = PERSONAS;
})();
