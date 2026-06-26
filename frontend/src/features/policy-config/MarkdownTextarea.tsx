/**
 * Section C: lightweight markdown textarea + preview toggle.
 *
 * Why roll our own instead of pulling react-markdown:
 *   - Adding a dep for two textareas in one drawer is overkill.
 *   - The supported feature set is intentionally tiny — paragraph breaks,
 *     bullet lists, bold/italic — which a 30-line render handles fine.
 *   - We keep full styling control matching antigravity tones.
 *
 * Supported markdown subset (rendered in preview mode):
 *   - Blank line separates paragraphs
 *   - Lines starting with "- " or "* " become bullet items
 *   - **bold** and *italic* inline
 *   - Everything else is plain text; HTML is escaped.
 *
 * If we ever need real markdown (tables, links, headings), swap to
 * react-markdown — the public API of this component stays the same.
 */
import React, { useMemo, useState } from 'react';

import { Button } from '../../components/antigravity/Button';
type Props = {
  label: string;
  value: string | null | undefined;
  onChange: (next: string | null) => void;
  disabled?: boolean;
  placeholder?: string;
  /** Optional helper hint shown beneath the textarea. */
  hint?: string;
  /** Min height in CSS pixels. Default 80. */
  minHeight?: number;
};

const escapeHtml = (s: string): string =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const renderInline = (s: string): string => {
  // Order matters: bold before italic, since ** would consume * first.
  const escaped = escapeHtml(s);
  const bolded = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  return bolded.replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>');
};

// Exported for the XSS-safety regression test (SEC-FE-5). All user input is
// HTML-escaped before the markdown regex runs, so only the controlled tag
// template (<strong>/<em>/<ul>/<li>/<p>/<br>) can ever reach the DOM.
export const renderMarkdown = (raw: string): string => {
  if (!raw.trim()) return '';
  const blocks = raw.split(/\n\s*\n/);
  const out: string[] = [];
  for (const block of blocks) {
    const lines = block.split('\n');
    const isList = lines.every((l) => /^\s*[-*]\s+/.test(l));
    if (isList) {
      const items = lines
        .map((l) => l.replace(/^\s*[-*]\s+/, ''))
        .map((l) => `<li>${renderInline(l)}</li>`)
        .join('');
      out.push(`<ul class="list-disc ml-4">${items}</ul>`);
    } else {
      const html = lines.map(renderInline).join('<br/>');
      out.push(`<p>${html}</p>`);
    }
  }
  return out.join('');
};

export const MarkdownTextarea: React.FC<Props> = ({
  label,
  value,
  onChange,
  disabled,
  placeholder,
  hint,
  minHeight = 80,
}) => {
  const [previewing, setPreviewing] = useState(false);
  const text = value || '';
  const html = useMemo(() => renderMarkdown(text), [text]);

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="block text-xs font-medium text-[#374151]">{label}</label>
        {!disabled && text.trim() && (
          <Button unstyled
            type="button"
            onClick={() => setPreviewing((p) => !p)}
            className="text-xs text-[#0b2b43] hover:underline"
          >
            {previewing ? 'Edit' : 'Preview'}
          </Button>
        )}
      </div>
      {previewing ? (
        <div
          className="prose prose-sm max-w-none rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm text-[#0b2b43]"
          style={{ minHeight }}
          dangerouslySetInnerHTML={{ __html: html || '<em>(empty)</em>' }}
        />
      ) : (
        <textarea
          className="w-full px-3 py-2 border border-[#d1d5db] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0b2b43] text-sm disabled:opacity-60"
          style={{ minHeight }}
          value={text}
          onChange={(e) => onChange(e.target.value || null)}
          disabled={disabled}
          placeholder={placeholder}
        />
      )}
      {hint && !previewing && (
        <p className="mt-1 text-xs text-[#6b7280]">{hint}</p>
      )}
    </div>
  );
};
