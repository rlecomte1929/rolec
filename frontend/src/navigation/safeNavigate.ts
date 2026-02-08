import type { NavigateFunction } from 'react-router-dom';
import { buildRoute, RouteKey, ROUTE_DEFS } from './routes';

const NAV_ERROR_KEY = 'relopass_nav_error';

export const setNavigationError = (message: string) => {
  localStorage.setItem(NAV_ERROR_KEY, message);
  window.dispatchEvent(new CustomEvent('nav-error', { detail: message }));
};

export const clearNavigationError = () => {
  localStorage.removeItem(NAV_ERROR_KEY);
  window.dispatchEvent(new CustomEvent('nav-error', { detail: '' }));
};

export const getNavigationError = () => localStorage.getItem(NAV_ERROR_KEY);

export const safeNavigate = (
  navigate: NavigateFunction,
  routeKey: RouteKey,
  params?: Record<string, string>
) => {
  if (!ROUTE_DEFS[routeKey]) {
    setNavigationError(`Missing route: ${routeKey}`);
    return;
  }
  clearNavigationError();
  navigate(buildRoute(routeKey, params));
};
