import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { initAnalytics } from './analytics';
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
import './index.css';

initAnalytics();
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
    console.error(err);
  }
}
