import React from 'react';
import ReactDOM from 'react-dom/client';
import { logger } from './lib/logger';
import App from './App';
import { initAnalytics, ensureTestDriveReplay } from './analytics';
import { initErrorTracking } from './lib/errorTracking';
// Self-hosted Inter (replaces the Google Fonts @import in index.css).
// GDPR: avoids sending every visitor's IP to Google's font CDN. Family name
// stays 'Inter', so no font-family references change. Weights match what the
// app uses (300-800); the browser fetches only the subsets it needs.
import '@fontsource/inter/300.css';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import '@fontsource/inter/800.css';
// JetBrains Mono — the brand mono font (DESIGN.md), used for code/data/IDs via
// `font-mono` and `--font-mono`. Self-hosted like Inter; only the weights the app
// uses (400/500/700) are loaded so the browser fetches only what it needs.
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import '@fontsource/jetbrains-mono/700.css';
import './index.css';

initAnalytics();
// TD-M2 (AIQ-1560): a returning tester lands with the session already stashed — start
// replay at boot. Sessions provisioned mid-visit are caught by TestDriveReplayGate.
ensureTestDriveReplay();
initErrorTracking();

const rootEl = document.getElementById('root');
if (!rootEl) {
  document.body.innerHTML = '<div style="padding:2rem;color:red;">Root element #root not found</div>';
} else {
  try {
    ReactDOM.createRoot(rootEl).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    rootEl.innerHTML = `<div style="padding:2rem;color:red;font-family:system-ui;">Failed to load: ${msg}</div>`;
    logger.error(err);
  }
}
