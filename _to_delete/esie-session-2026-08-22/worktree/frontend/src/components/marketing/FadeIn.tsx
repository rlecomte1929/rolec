import React, { useRef, useState, useEffect } from 'react';

interface FadeInProps {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}

/**
 * Wraps content with a scroll-triggered fade-in + rise entrance.
 * - Respects prefers-reduced-motion: skips animation entirely.
 * - If the element is already in the viewport on mount, appears instantly.
 * - Once visible, the observer is disconnected (animation fires once only).
 */
export const FadeIn: React.FC<FadeInProps> = ({
  children,
  delay = 0,
  className = '',
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const prefersReduced = window.matchMedia(
      '(prefers-reduced-motion: reduce)'
    ).matches;
    if (prefersReduced) {
      setVisible(true);
      return;
    }

    const el = ref.current;
    if (!el) return;

    const rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight * 0.95) {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setVisible(true);
          observer.unobserve(el);
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(24px)',
        transition: visible
          ? `opacity 350ms ease-out ${delay}ms, transform 350ms ease-out ${delay}ms`
          : 'none',
      }}
    >
      {children}
    </div>
  );
};
