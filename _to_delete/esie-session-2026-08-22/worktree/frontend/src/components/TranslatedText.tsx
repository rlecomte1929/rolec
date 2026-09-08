import React, { useEffect, useState } from 'react';
import { translateText, type TranslationDomain } from '../api/translation';
import { Badge } from './antigravity/Badge';

interface TranslatedTextProps {
  text: string;
  /** Source language (BCP-47). */
  src: string;
  /** Target language (BCP-47). When equal to `src` or empty, the original is shown untranslated. */
  tgt: string;
  domain?: TranslationDomain;
  /** Render the "Translated" badge alongside the text (default true). */
  showBadge?: boolean;
  className?: string;
}

/**
 * Renders document content translated into the viewer's preferred language, with a
 * "Translated" badge. Shows the original immediately and on any error (graceful
 * degradation — translation never blocks the content).
 */
export const TranslatedText: React.FC<TranslatedTextProps> = ({
  text,
  src,
  tgt,
  domain = 'comm',
  showBadge = true,
  className,
}) => {
  const [translated, setTranslated] = useState<string | null>(null);

  const shouldTranslate = Boolean(text) && Boolean(tgt) && tgt !== src;

  useEffect(() => {
    let cancelled = false;
    if (!shouldTranslate) {
      setTranslated(null);
      return;
    }
    translateText({ text, src, tgt, domain })
      .then((res) => {
        if (!cancelled) setTranslated(res.text);
      })
      .catch(() => {
        if (!cancelled) setTranslated(null); // fall back to the original
      });
    return () => {
      cancelled = true;
    };
  }, [text, src, tgt, domain, shouldTranslate]);

  const isTranslated = translated !== null && translated !== text;

  return (
    <span className={className}>
      {translated ?? text}
      {showBadge && isTranslated && (
        <>
          {' '}
          <Badge variant="info" size="sm">Translated</Badge>
        </>
      )}
    </span>
  );
};
