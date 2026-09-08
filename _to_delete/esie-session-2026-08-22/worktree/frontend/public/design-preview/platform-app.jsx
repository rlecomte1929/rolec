// platform-app.jsx — main App that ties shell + screens + tweaks together
(function() {
const { useState, useEffect } = React;
const I = window.PlatformIcon;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "route": "s0",
  "demo": "marc",
  "sbCollapsed": false,
  "role": "admin",
  "authVariant": "split",
  "authAnimated": true,
  "authMode": "login",
  "authState": "idle",
  "authClaim": false,
  "companiesState": "idle",
  "profileMode": "filled",
  "profileZoom": "",
  "profileLogoState": "",
  "excTradeoffs": false,
  "intakeEdge": "family",
  "intakeNotes": false,
  "intakeTier": "standard",
  "platformCurrency": "EUR"
}/*EDITMODE-END*/;

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [aiOpen, setAiOpen] = useState(false);

  // Apply theme to <html>
  useEffect(() => {
    document.documentElement.dataset.theme = t.theme;
  }, [t.theme]);

  // Keyboard shortcut for AI
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'j') { e.preventDefault(); setAiOpen(o => !o); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Listen for sub-nav route changes posted by child screens
  useEffect(() => {
    const handler = (e) => setTweak('route', e.detail);
    window.addEventListener('platform-set-route', handler);
    return () => window.removeEventListener('platform-set-route', handler);
  }, []);

  const route = t.route;
  const setRoute = (r) => setTweak('route', r);

  // Preset answers for S1 wizard depending on demo
  const presets = {
    blank: null,
    marc:  { origin: 'FR', destination: 'NO', purpose: 'work', employee_type: 'permanent', contract: '6w', family: 'partner_kids' },
    priya: { origin: 'IN', destination: 'DE', purpose: 'work', employee_type: 'permanent', contract: '6mo', family: 'solo' },
  };

  // ── Auth route (s0) ───────────────────────────────────────────────
  // Full-bleed: no sidebar, no topbar, no AI panel. After auth, route
  // to the persona's home (S9 admin / S7 HR / S3 employee), per spec §5.
  if (route === 's0') {
    return (
      <>
        <AuthScreen
          variant={t.authVariant}
          animated={t.authAnimated}
          initialMode={t.authMode}
          initialState={t.authState}
          claimToken={t.authClaim ? 'a4f2b9d1-7c83-4e09c' : null}
          dark={t.theme === 'dark'}
          onToggleTheme={() => setTweak('theme', t.theme === 'dark' ? 'light' : 'dark')}
          onAuthenticated={(persona) => {
            // Per spec §4, write localStorage. Per §5, route by role.
            try {
              localStorage.setItem('relopass_token', 'demo-' + Math.random().toString(36).slice(2));
              localStorage.setItem('relopass_role', persona.role);
              localStorage.setItem('relopass_email', persona.email);
              localStorage.setItem('relopass_name', persona.name);
              localStorage.setItem('relopass_user_id', 'demo-uid-' + persona.role.toLowerCase());
            } catch (e) { /* ignore */ }
            setTweak({
              role: persona.sidebarRole,
              route: persona.route,
              authState: 'idle',
              authMode: 'login',
              authClaim: false,
            });
          }}
        />
        {renderTweaks(t, setTweak, aiOpen, setAiOpen, route)}
      </>
    );
  }

  // ── Authenticated app shell ───────────────────────────────────────
  return (
    <div className={`app${aiOpen ? ' ai-open' : ''}${t.sbCollapsed ? ' sb-collapsed' : ''}`}>
      <Sidebar route={route} setRoute={setRoute}
               role={t.role}
               collapsed={t.sbCollapsed}
               onToggleCollapse={() => setTweak('sbCollapsed', !t.sbCollapsed)} />
      <div className="main">
        <TopBar route={route} onOpenAI={() => setAiOpen(true)}
                onToggleTheme={() => setTweak('theme', t.theme === 'dark' ? 'light' : 'dark')}
                dark={t.theme === 'dark'}
                onSignOut={() => {
                  try {
                    ['relopass_token','relopass_role','relopass_email','relopass_name','relopass_user_id','relopass_username']
                      .forEach(k => localStorage.removeItem(k));
                  } catch (e) {}
                  setTweak({ route: 's0', authState: 'idle', authMode: 'login' });
                }}/>
        {route === 's1' && <IntakeScreen presetAnswers={presets[t.demo]} onComplete={() => setRoute('s3')} />}
        {route === 's1n' && <QuickIntakeScreen edge={t.intakeEdge} showNotes={t.intakeNotes} onComplete={() => setRoute('s1p')}/>}
        {route === 's1p' && <ProfileRichScreen edge={t.intakeEdge} showNotes={t.intakeNotes} tier={t.intakeTier}/>}
        {route === 's1f' && <IntakeFlowDiagram/>}
        {route === 's2' && <DiscoveryScreen />}
        {route === 's3' && <RoadmapScreen />}
        {route === 's4' && <DossierScreen />}
        {route === 's5' && <PolicyScreen />}
        {route === 's5b' && <PolicyBuilderScreen currency={t.platformCurrency}/>}
        {route === 's5c' && <PolicyRealityScreen currency={t.platformCurrency}/>}
        {route === 's6' && <MarketplaceScreen />}
        {route === 's7' && <ControlScreen />}
        {route === 's7p' && <CompanyProfileScreen initialMode={t.profileMode} initialZoom={t.profileZoom} initialLogoState={t.profileLogoState}/>}
        {route === 's7e' && <ExceptionsScreen tradeoffNotes={t.excTradeoffs}/>}
        {route === 's8' && <DocumentsScreen />}
        {route === 's10' && <InboxScreen />}
        {route === 's9'  && <AdminOverviewScreen setRoute={setRoute}/>}
        {route === 's9a' && <ReviewQueueScreen />}
        {route === 's9b' && <OpsAnalyticsScreen />}
        {route === 's9c' && <WorkflowAnalyticsScreen />}
        {route === 's9d' && <ResourcesCMSScreen />}
        {route === 's9e' && <ProspectsScreen />}
        {route === 's9f' && <IntegrationsScreen />}
        {route === 's9g' && <CompaniesScreen initialState={t.companiesState}/>}
      </div>
      {aiOpen && <AIPanel route={route} onClose={() => setAiOpen(false)} />}
      {!aiOpen && <AIFab onClick={() => setAiOpen(true)} />}

      {renderTweaks(t, setTweak, aiOpen, setAiOpen, route)}
    </div>
  );
}

function renderTweaks(t, setTweak, aiOpen, setAiOpen, route) {
  const isAuth = route === 's0';
  return (
    <TweaksPanel>
      <TweakSection label="Screen" />
      <TweakSelect label="Page" value={route}
        options={[
          { value: 's0', label: 'S0 · Sign-in / Sign-up' },
          { value: 's1', label: 'S1 · Intake wizard (original)' },
          { value: 's1n', label: 'S1n · Detailed Intake (redesign)' },
          { value: 's1p', label: 'S1p · Rich profile' },
          { value: 's1f', label: 'S1f · Flow diagram (annotated)' },
          { value: 's2', label: 'S2 · AI requirements discovery' },
          { value: 's3', label: 'S3 · Roadmap (Employee home)' },
          { value: 's10', label: 'S10 · Inbox' },
          { value: 's8', label: 'S8 · Documents' },
          { value: 's4', label: 'S4 · Dossier & forms' },
          { value: 's6', label: 'S6 · Service marketplace' },
          { value: 's7', label: 'S7 · HR control (HR home)' },
          { value: 's7p', label: 'S7p · Company profile (HR)' },
          { value: 's7e', label: 'S7e · Policy exceptions (HR)' },
          { value: 's5', label: 'S5 · Policy & benefits (employee)' },
          { value: 's5b', label: 'S5b · Policy Builder (HR)' },
          { value: 's5c', label: 'S5c · Policy vs. Reality (HR)' },
          { value: 's9', label: 'S9 · Admin overview (Admin home)' },
          { value: 's9g', label: 'S9g · Companies (admin)' },
        ]}
        onChange={(v) => setTweak('route', v)} />

      {isAuth && <>
        <TweakSection label="Auth layout" />
        <TweakRadio label="Variant" value={t.authVariant}
          options={[
            { value: 'split',  label: 'Split + map' },
            { value: 'center', label: 'Centered' },
          ]}
          onChange={(v) => setTweak('authVariant', v)} />

        <TweakToggle label="Animated corridor map"
          value={t.authAnimated}
          onChange={(v) => setTweak('authAnimated', v)} />

        <TweakSection label="Auth flow" />
        <TweakRadio label="Mode" value={t.authMode}
          options={[
            { value: 'login',    label: 'Sign in' },
            { value: 'register', label: 'Sign up' },
          ]}
          onChange={(v) => setTweak('authMode', v)} />

        <TweakToggle label="Invite-claim flow (?claim_token)"
          value={t.authClaim}
          onChange={(v) => setTweak('authClaim', v)} />

        <TweakSelect label="Initial state" value={t.authState}
          options={[
            { value: 'idle',        label: 'Idle (form ready)' },
            { value: 'loading',     label: 'Loading…' },
            { value: 'error-401',   label: 'Error · wrong credentials' },
            { value: 'error-taken', label: 'Error · email already used' },
            { value: 'error-429',   label: 'Error · rate limited' },
          ]}
          onChange={(v) => setTweak('authState', v)} />

        <TweakSection label="Try it" />
        <div style={{ fontSize: 11.5, color: 'var(--text-3)', lineHeight: 1.5, padding: '4px 2px 0' }}>
          Type anything &amp; click sign in to see persona routing.
          Or use the one-click demo buttons inside the form to jump straight to each persona's home screen.
        </div>
      </>}

      {!isAuth && (route === 's1n' || route === 's1p' || route === 's1f') && <>
        <TweakSection label="Intake redesign" />
        <TweakSelect label="Edge case" value={t.intakeEdge}
          options={[
            { value: 'family',    label: 'Family (partner + 2 kids)' },
            { value: 'solo',      label: 'Solo (just me)' },
            { value: 'large',     label: 'Large family (4 kids + 2 dogs)' },
            { value: 'uk_jp_pet', label: 'UK→JP w/ Rottweiler' },
          ]}
          onChange={(v) => setTweak('intakeEdge', v)} />
        <TweakToggle label="Show UX tradeoff notes"
          value={t.intakeNotes}
          onChange={(v) => setTweak('intakeNotes', v)} />
        <TweakRadio label="Plan tier" value={t.intakeTier}
          options={[
            { value: 'basic',    label: 'Basic' },
            { value: 'standard', label: 'Standard' },
            { value: 'premium',  label: 'Premium' },
          ]}
          onChange={(v) => setTweak('intakeTier', v)} />
      </>}

      {!isAuth && route === 's7e' && <>
        <TweakSection label="Exceptions screen" />
        <TweakToggle label="Show UX tradeoff notes"
          value={t.excTradeoffs}
          onChange={(v) => setTweak('excTradeoffs', v)} />
      </>}

      {!isAuth && route === 's7p' && <>
        <TweakSection label="Profile screen" />
        <TweakRadio label="State" value={t.profileMode}
          options={[
            { value: 'filled', label: 'Filled / populated' },
            { value: 'empty',  label: 'Empty welcome' },
            { value: 'wizard', label: '3-step wizard' },
          ]}
          onChange={(v) => setTweak({ profileMode: v, profileLogoState: '', profileZoom: '' })} />
        <TweakRadio label="Logo state" value={t.profileLogoState || 'auto'}
          options={[
            { value: 'auto',      label: 'Auto' },
            { value: 'empty',     label: 'Empty' },
            { value: 'uploading', label: 'Uploading' },
            { value: 'uploaded',  label: 'Uploaded' },
          ]}
          onChange={(v) => setTweak('profileLogoState', v === 'auto' ? '' : v)} />
        <TweakSelect label="Zoom section" value={t.profileZoom || ''}
          options={[
            { value: '',  label: 'None' },
            { value: 'A', label: 'A · Identity' },
            { value: 'B', label: 'B · Location' },
            { value: 'C', label: 'C · HR & Mobility' },
            { value: 'D', label: 'D · Branding' },
          ]}
          onChange={(v) => setTweak('profileZoom', v)} />
      </>}

      {!isAuth && route === 's9g' && <>
        <TweakSection label="Companies screen" />
        <TweakRadio label="State" value={t.companiesState}
          options={[
            { value: 'idle',    label: 'Loaded' },
            { value: 'loading', label: 'Loading' },
            { value: 'error',   label: 'Error' },
          ]}
          onChange={(v) => setTweak('companiesState', v)} />
      </>}

      {!isAuth && <>
        <TweakSection label="Role / plan" />
        <TweakSelect label="View as" value={t.role}
          options={[
            { value: 'basic',    label: 'Employee · Basic plan' },
            { value: 'standard', label: 'Employee · Standard plan' },
            { value: 'premium',  label: 'Employee · Premium plan' },
            { value: 'hr',       label: 'HR / Mobility lead' },
            { value: 'admin',    label: 'ReloPass admin (full)' },
          ]}
          onChange={(v) => setTweak('role', v)} />

        <TweakSection label="Demo data" />
        <TweakRadio label="Intake state" value={t.demo}
          options={[
            { value: 'blank', label: 'Empty' },
            { value: 'marc',  label: 'Marc · FR→NO' },
            { value: 'priya', label: 'Priya · IN→DE' },
          ]}
          onChange={(v) => setTweak('demo', v)} />

        <TweakSection label="AI panel" />
        <TweakToggle label="Open" value={aiOpen} onChange={setAiOpen}/>

        <TweakSection label="Layout" />
        <TweakToggle label="Collapse sidebar" value={t.sbCollapsed} onChange={(v) => setTweak('sbCollapsed', v)}/>
      </>}

      <TweakSection label="Platform" />
      <TweakRadio label="Default currency" value={t.platformCurrency}
        options={[
          { value: 'EUR', label: '€ EUR' },
          { value: 'USD', label: '$ USD' },
          { value: 'GBP', label: '£ GBP' },
          { value: 'CHF', label: 'CHF' },
        ]}
        onChange={(v) => setTweak('platformCurrency', v)} />

      <TweakSection label="Theme" />
      <TweakRadio label="Mode" value={t.theme}
        options={['light', 'dark']}
        onChange={(v) => setTweak('theme', v)} />

      {!isAuth && (
        <>
          <TweakSection label="Session" />
          <TweakButton label="Return to sign-in" onClick={() => setTweak({ route: 's0', authState: 'idle', authMode: 'login' })} />
        </>
      )}
    </TweaksPanel>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
})();
