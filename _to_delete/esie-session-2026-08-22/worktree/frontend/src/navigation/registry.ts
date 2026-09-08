import { useEffect } from 'react';
import type { RouteKey } from './routes';

export type NavItem = {
  label: string;
  routeKey: RouteKey;
  notes?: string;
};

const registry = new Map<string, NavItem[]>();

export const registerNavItems = (pageId: string, items: NavItem[]) => {
  registry.set(pageId, items);
};

export const unregisterNavItems = (pageId: string) => {
  registry.delete(pageId);
};

export const getNavRegistry = () => {
  return Array.from(registry.entries()).map(([pageId, items]) => ({
    pageId,
    items,
  }));
};

export const useRegisterNav = (pageId: string, items: NavItem[]) => {
  useEffect(() => {
    registerNavItems(pageId, items);
    return () => unregisterNavItems(pageId);
  }, [pageId, items]);
};
