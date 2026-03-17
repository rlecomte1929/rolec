import React, { useState, useEffect, useCallback } from 'react';

const SCROLL_THRESHOLD_RATIO = 0.3;

export const BackToTop: React.FC = () => {
  const [visible, setVisible] = useState(false);

  const handleScroll = useCallback(() => {
    const threshold = window.innerHeight * SCROLL_THRESHOLD_RATIO;
    setVisible(window.scrollY > threshold);
  }, []);

  useEffect(() => {
    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [handleScroll]);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  if (!visible) return null;

  return (
    <button
      type="button"
      onClick={scrollToTop}
      aria-label="Back to top"
      className="fixed bottom-20 right-4 sm:bottom-8 sm:right-8 z-40 flex items-center gap-2 rounded-full border border-marketing-border bg-marketing-surface px-3 py-2 sm:px-4 sm:py-2.5 text-xs sm:text-sm font-medium text-marketing-text-muted shadow-sm transition-all duration-200 hover:border-marketing-border hover:bg-marketing-surface-muted hover:text-marketing-primary focus:outline-none focus:ring-2 focus:ring-marketing-accent focus:ring-offset-2 animate-fade-in"
    >
      <svg
        className="h-4 w-4 shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M5 10l7-7m0 0l7 7m-7-7v18"
        />
      </svg>
      <span>Back to top</span>
    </button>
  );
};
