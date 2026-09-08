import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { ReloPassMarketingLanding, UnavailableFeature } from '../../components/ReloPassSharedSurface';
import CaseCommand from '../case-command/App';
import MoveRoadmaps from '../move-roadmaps/App';
import { ReloPassShell } from './ReloPassShell';
import { PublicPageView } from './publicPages';
import {
  getDefaultRoute,
  navigateTo,
  parseHashRoute,
  type ParsedRoute,
} from './routes';

function useHashRoute(): ParsedRoute {
  const [hash, setHash] = useState(() => window.location.hash || `#${getDefaultRoute()}`);

  useEffect(() => {
    const onChange = () => setHash(window.location.hash || `#${getDefaultRoute()}`);
    window.addEventListener('hashchange', onChange);
    if (!window.location.hash) {
      navigateTo(getDefaultRoute());
    }
    return () => window.removeEventListener('hashchange', onChange);
  }, []);

  return useMemo(() => parseHashRoute(hash), [hash]);
}

function RouteBody({ route }: { route: ParsedRoute }) {
  const { def } = route;

  if (def.kind === 'landing') {
    return (
      <ReloPassMarketingLanding
        scrollRootClass="main-landing-root"
        onPrimaryCta={() => navigateTo('/get-started')}
        onSecondaryCta={() => {
          window.location.href = 'mailto:contact@relopass.com?subject=Book%20a%20demo';
        }}
        onSignIn={() => navigateTo('/auth')}
        onPlatformTour={() => navigateTo('/platform')}
      />
    );
  }

  if (def.kind === 'public' && def.publicKey) {
    return <PublicPageView pageKey={def.publicKey} />;
  }

  if (def.kind === 'demo-case-command') {
    return (
      <div className="min-h-full">
        <div
          className="px-4 py-2 text-xs border-b"
          style={{
            backgroundColor: 'var(--space-brand-primary-50)',
            borderColor: 'var(--space-border-default)',
            color: 'var(--space-text-secondary)',
          }}
        >
          Live demo data — Case Command (HR case management hub). Backend APIs and WorkspaceDB persistence are not connected in this draft.
        </div>
        <CaseCommand />
      </div>
    );
  }

  if (def.kind === 'demo-move-roadmaps') {
    return (
      <div className="min-h-full">
        <div
          className="px-4 py-2 text-xs border-b"
          style={{
            backgroundColor: 'var(--space-brand-primary-50)',
            borderColor: 'var(--space-border-default)',
            color: 'var(--space-text-secondary)',
          }}
        >
          Live demo data — Move Roadmaps (employee relocation journey). Commute maps (Leaflet) and live case sync are unavailable in Audos.
        </div>
        <MoveRoadmaps />
      </div>
    );
  }

  return (
    <UnavailableFeature
      title={def.label}
      reason={def.unavailableReason || 'This imported route is not yet available in the native Audos recreation.'}
      detail="The original ReloPass app relied on a Python FastAPI backend, Supabase auth/realtime, and npm packages not on the Audos CDN. Server-functions and WorkspaceDB tables must be registered before this surface can go live."
      unmappableId={def.unmappableId}
    />
  );
}

export default function App() {
  const route = useHashRoute();
  const path = route.def.path;
  const isFullBleedLanding = route.def.kind === 'landing';

  if (isFullBleedLanding) {
    return (
      <div className="main-landing-root h-full overflow-y-auto">
        <RouteBody route={route} />
      </div>
    );
  }

  return (
    <ReloPassShell currentPath={path}>
      <RouteBody route={route} />
    </ReloPassShell>
  );
}
