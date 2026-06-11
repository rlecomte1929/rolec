import { useEffect } from 'react';

interface PageMeta {
  title: string;
  description: string;
  ogTitle?: string;
  ogDescription?: string;
  ogImage?: string;
  ogUrl?: string;
  /** og:image dimensions + alt (FRIDAY-004d §4) */
  ogImageWidth?: string;
  ogImageHeight?: string;
  ogImageAlt?: string;
  /** og:locale, e.g. 'en_GB' (FRIDAY-004d §4) */
  ogLocale?: string;
  /** twitter:site / twitter:creator handles, e.g. '@relopass' (FRIDAY-004d §6) */
  twitterSite?: string;
  twitterCreator?: string;
  /** schema.org JSON-LD object injected as <script type="application/ld+json"> */
  jsonLd?: Record<string, unknown>;
}

const SITE_NAME = 'ReloPass';
const DEFAULT_OG_IMAGE = '/screenshot-hero-case-card.png';
const BASE_URL = 'https://www.relopass.com';
const JSON_LD_ID = 'page-jsonld';

/** Absolute URLs pass through; site-relative paths get the canonical host. */
const resolveImage = (img: string) => (/^https?:\/\//.test(img) ? img : `${BASE_URL}${img}`);

/**
 * Set page-level <title> + meta tags (description, Open Graph, Twitter Card,
 * optional og:image dimensions/locale and schema.org JSON-LD).
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
  ogImageWidth,
  ogImageHeight,
  ogImageAlt,
  ogLocale,
  twitterSite,
  twitterCreator,
  jsonLd,
}: PageMeta) {
  const jsonLdStr = jsonLd ? JSON.stringify(jsonLd) : '';
  useEffect(() => {
    document.title = title;
    const imageUrl = resolveImage(ogImage);

    // Helper: ensure a meta tag with the given attribute matcher exists, then
    // set its content. attrName/attrValue identify the tag (name or property).
    const setMeta = (attrName: 'name' | 'property', attrValue: string, content?: string) => {
      const selector = `meta[${attrName}="${attrValue}"]`;
      let el = document.querySelector<HTMLMetaElement>(selector);
      if (content === undefined) {
        el?.remove();
        return;
      }
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
    setMeta('property', 'og:image', imageUrl);
    setMeta('property', 'og:image:width', ogImageWidth);
    setMeta('property', 'og:image:height', ogImageHeight);
    setMeta('property', 'og:image:alt', ogImageAlt);
    setMeta('property', 'og:url', ogUrl ?? BASE_URL);
    setMeta('property', 'og:type', 'website');
    setMeta('property', 'og:site_name', SITE_NAME);
    setMeta('property', 'og:locale', ogLocale);
    setMeta('name', 'twitter:card', 'summary_large_image');
    setMeta('name', 'twitter:site', twitterSite);
    setMeta('name', 'twitter:creator', twitterCreator);
    setMeta('name', 'twitter:title', ogTitle ?? title);
    setMeta('name', 'twitter:description', ogDescription ?? description);
    setMeta('name', 'twitter:image', imageUrl);
    setMeta('name', 'twitter:image:alt', ogImageAlt);

    // schema.org JSON-LD: manage a single page-scoped <script>. Set when provided,
    // remove when a subsequent page navigates in without one (avoids stale markup).
    const existing = document.getElementById(JSON_LD_ID);
    if (jsonLdStr) {
      const el = (existing as HTMLScriptElement | null) ?? document.createElement('script');
      el.id = JSON_LD_ID;
      el.setAttribute('type', 'application/ld+json');
      el.textContent = jsonLdStr;
      if (!existing) document.head.appendChild(el);
    } else {
      existing?.remove();
    }
  }, [
    title,
    description,
    ogTitle,
    ogDescription,
    ogImage,
    ogUrl,
    ogImageWidth,
    ogImageHeight,
    ogImageAlt,
    ogLocale,
    twitterSite,
    twitterCreator,
    jsonLdStr,
  ]);
}
