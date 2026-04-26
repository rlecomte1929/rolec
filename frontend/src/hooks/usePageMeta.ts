import { useEffect } from 'react';

interface PageMeta {
  title: string;
  description: string;
  ogTitle?: string;
  ogDescription?: string;
  ogImage?: string;
  ogUrl?: string;
}

const SITE_NAME = 'ReloPass';
const DEFAULT_OG_IMAGE = '/screenshot-hero-case-card.png';
const BASE_URL = 'https://www.relopass.com';

/**
 * Set page-level <title> + meta tags (description, Open Graph, Twitter Card).
 * Mutates document.head directly. Safe to call from any page component;
 * each navigation overwrites the previous values.
 */
export function usePageMeta({
  title,
  description,
  ogTitle,
  ogDescription,
  ogImage = DEFAULT_OG_IMAGE,
  ogUrl,
}: PageMeta) {
  useEffect(() => {
    document.title = title;

    // Helper: ensure a meta tag with the given attribute matcher exists, then
    // set its content. attrName/attrValue identify the tag (name or property).
    const setMeta = (attrName: 'name' | 'property', attrValue: string, content: string) => {
      const selector = `meta[${attrName}="${attrValue}"]`;
      let el = document.querySelector<HTMLMetaElement>(selector);
      if (!el) {
        el = document.createElement('meta');
        el.setAttribute(attrName, attrValue);
        document.head.appendChild(el);
      }
      el.setAttribute('content', content);
    };

    setMeta('name', 'description', description);
    setMeta('property', 'og:title', ogTitle ?? title);
    setMeta('property', 'og:description', ogDescription ?? description);
    setMeta('property', 'og:image', `${BASE_URL}${ogImage}`);
    setMeta('property', 'og:url', ogUrl ?? BASE_URL);
    setMeta('property', 'og:type', 'website');
    setMeta('property', 'og:site_name', SITE_NAME);
    setMeta('name', 'twitter:card', 'summary_large_image');
    setMeta('name', 'twitter:title', ogTitle ?? title);
    setMeta('name', 'twitter:description', ogDescription ?? description);
    setMeta('name', 'twitter:image', `${BASE_URL}${ogImage}`);
  }, [title, description, ogTitle, ogDescription, ogImage, ogUrl]);
}
