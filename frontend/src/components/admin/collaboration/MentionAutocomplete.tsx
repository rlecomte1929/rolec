import React, { useCallback, useEffect, useRef, useState } from 'react';
import { adminReviewQueueAPI } from '../../../api/client';

type User = { id: string; email?: string; full_name?: string };

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
  minChars?: number;
}

export const MentionAutocomplete: React.FC<Props> = ({
  value,
  onChange,
  placeholder = 'Add a comment... Use @ to mention someone.',
  rows = 2,
  disabled = false,
  minChars = 1,
}) => {
  const [users, setUsers] = useState<User[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [mentionStart, setMentionStart] = useState<number | null>(null);
  const [filter, setFilter] = useState('');
  const [highlightIdx, setHighlightIdx] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    adminReviewQueueAPI.getAssignees(50).then((r) => {
      setUsers((r.items as User[]) || []);
    }).catch(() => setUsers([]));
  }, []);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const v = e.target.value;
    const selStart = e.target.selectionStart ?? v.length;
    onChange(v);

    // Find @ before cursor
    const beforeCursor = v.slice(0, selStart);
    const atMatch = beforeCursor.match(/@([^\s@]*)$/);
    if (atMatch) {
      setMentionStart(selStart - atMatch[0].length);
      setFilter(atMatch[1].toLowerCase());
      setShowDropdown(atMatch[1].length >= minChars || atMatch[1].length === 0);
      setHighlightIdx(0);
    } else {
      setShowDropdown(false);
      setMentionStart(null);
    }
  }, [onChange, minChars]);

  const filtered = users.filter((u) => {
    const email = (u.email || '').toLowerCase();
    const name = (u.full_name || '').toLowerCase();
    const id = (u.id || '').toLowerCase();
    if (!filter) return true;
    return email.includes(filter) || name.includes(filter) || id.includes(filter);
  }).slice(0, 8);

  const insertMention = useCallback((user: User) => {
    if (mentionStart === null) return;
    const insert = `@${user.email || user.id} `;
    const before = value.slice(0, mentionStart);
    const after = value.slice(mentionStart);
    const remainder = after.replace(/@[^\s@]*/, '');
    const next = before + insert + remainder;
    onChange(next);
    setShowDropdown(false);
    setMentionStart(null);
    textareaRef.current?.focus();
    const newPos = mentionStart + insert.length;
    setTimeout(() => textareaRef.current?.setSelectionRange(newPos, newPos), 0);
  }, [value, mentionStart, onChange]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!showDropdown || filtered.length === 0) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightIdx((i) => (i + 1) % filtered.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightIdx((i) => (i - 1 + filtered.length) % filtered.length);
      } else if (e.key === 'Enter' && filtered[highlightIdx]) {
        e.preventDefault();
        insertMention(filtered[highlightIdx]);
      } else if (e.key === 'Escape') {
        setShowDropdown(false);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [showDropdown, filtered, highlightIdx, insertMention]);

  useEffect(() => {
    setHighlightIdx(0);
  }, [filter]);

  return (
    <div className="relative w-full">
      <textarea
        ref={textareaRef}
        className="w-full rounded border border-slate-300 p-2 text-sm"
        rows={rows}
        placeholder={placeholder}
        value={value}
        onChange={handleChange}
        disabled={disabled}
        onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
      />
      {showDropdown && filtered.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-10 mt-0.5 max-h-40 w-full overflow-auto rounded border border-slate-200 bg-white py-1 shadow-lg"
        >
          {filtered.map((u, i) => (
            <button
              key={u.id}
              type="button"
              className={`block w-full px-2 py-1 text-left text-sm hover:bg-slate-100 ${
                i === highlightIdx ? 'bg-slate-100' : ''
              }`}
              onMouseDown={(e) => {
                e.preventDefault();
                insertMention(u);
              }}
            >
              {u.full_name || u.email || u.id}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
