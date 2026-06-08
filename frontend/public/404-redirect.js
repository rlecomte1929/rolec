// SPA deep-link restore. Kept as an EXTERNAL script (not inline in 404.html) so
// it satisfies the production CSP `script-src 'self'` (which has no
// 'unsafe-inline' — inline scripts are blocked). Same-origin /404-redirect.js is
// allowed by 'self'.
//
// Static hosts (Render) serve 404.html for any path that isn't a real file
// (e.g. /hr/command-center on hard load / refresh / bookmark). We preserve the
// requested path in ?__redirect= and bounce to "/", where App.tsx's
// <QueryRedirect> reads __redirect and routes to it.
(function () {
  var path = window.location.pathname + window.location.search + window.location.hash;
  window.location.replace('/?__redirect=' + encodeURIComponent(path));
})();
