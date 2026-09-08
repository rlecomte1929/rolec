import React from 'react';

/** Bold segments marked with **text** (backend copy convention). */
export function formatRichMessage(text: string): React.ReactNode {
  if (!text.includes('**')) return text;
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    const m = p.match(/^\*\*([^*]+)\*\*$/);
    if (m) {
      return (
        <strong key={i} className="font-semibold text-[#0b2b43]">
          {m[1]}
        </strong>
      );
    }
    return <span key={i}>{p}</span>;
  });
}
