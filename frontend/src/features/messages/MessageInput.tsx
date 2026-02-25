import React, { useState, useRef, useCallback } from 'react';

interface MessageInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export const MessageInput: React.FC<MessageInputProps> = ({
  onSend,
  disabled = false,
  placeholder = 'Type a message…',
}) => {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const trimmed = text.trim();
        if (trimmed) {
          onSend(trimmed);
          setText('');
        }
      }
    },
    [text, onSend]
  );

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (trimmed) {
      onSend(trimmed);
      setText('');
      textareaRef.current?.focus();
    }
  }, [text, onSend]);

  return (
    <div
      className="sticky bottom-0 left-0 right-0 bg-white border-t border-[#e2e8f0] p-4 shadow-[0_-4px_12px_rgba(0,0,0,0.04)]"
      role="form"
      aria-label="Send message"
    >
      <div className="flex items-end gap-2">
        <button
          type="button"
          className="flex-shrink-0 p-2 rounded-full text-[#6b7280] hover:bg-[#f5f7fa] hover:text-[#1A1A1A] transition-colors"
          aria-label="Attach file"
          disabled={disabled}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
          </svg>
        </button>
        <div className="flex-1 min-w-0">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className="w-full resize-none rounded-2xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-[15px] text-[#1A1A1A] placeholder:text-[#94a3b8] focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/20 focus:border-[#0b2b43] min-h-[44px] max-h-[120px]"
            style={{ minHeight: '44px' }}
            aria-label="Message text"
          />
        </div>
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="flex-shrink-0 p-2.5 rounded-full bg-[#0b2b43] text-white hover:bg-[#1e3a5f] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Send message"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
      <p className="mt-2 text-[11px] text-[#94a3b8] hidden sm:block" aria-hidden>
        Enter to send · Shift+Enter for new line
      </p>
    </div>
  );
};
