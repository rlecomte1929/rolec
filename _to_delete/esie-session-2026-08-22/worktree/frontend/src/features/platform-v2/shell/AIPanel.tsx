/**
 * AIPanel.tsx — ReloPass Platform AI Assistant Panel
 * ─────────────────────────────────────────────────────────────────────────────
 * - Fixed right drawer, 360px width, full viewport height
 * - Slides in from right; main content shrinks to accommodate
 * - Route-aware context strip + suggested prompt chips
 * - Chat history with user/AI message bubbles
 * - Streaming simulation via window.claude?.complete() or built-in fallback
 * - Close on Escape
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
// ─── Constants ────────────────────────────────────────────────────────────────

const CLAUDE_MODEL = 'claude-haiku-4-5-20251001' as const;

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: Date;
  /** Streaming in progress */
  streaming?: boolean;
}

export interface AIPanelProps {
  /** Whether the panel is open */
  open: boolean;
  /** Current route path, e.g. '/roadmap' or '/cases/abc/documents' */
  route: string;
  /** Close callback */
  onClose: () => void;
}

// ─── Route context map ────────────────────────────────────────────────────────

interface RouteContext {
  context: string;
  chips: string[];
}

const ROUTE_AI_CONTEXT: Record<string, RouteContext> = {
  '/dashboard': {
    context: "I can summarise what needs your attention today, or answer questions about any case.",
    chips: ["What's urgent today?", 'How many open cases?', 'Summarise recent activity'],
  },
  '/roadmap': {
    context: "I can explain any step, suggest what to tackle next, or draft a message to a vendor.",
    chips: ['What should I do next?', 'Explain the current step', 'Draft a vendor message'],
  },
  '/discovery': {
    context: "I can explain any requirement, help you find missing documents, or assess your eligibility.",
    chips: ['What documents do I need?', 'Explain this requirement', 'Am I eligible?'],
  },
  '/dossier': {
    context: "I can review your dossier for completeness, flag gaps, or suggest what to upload next.",
    chips: ["Is my dossier complete?", "What's still missing?", 'Review my forms'],
  },
  '/documents': {
    context: "I can help you find a document, explain what it's for, or check its status.",
    chips: ['Find my visa documents', 'What is this document for?', 'Check pending approvals'],
  },
  '/policy': {
    context: "I can explain your policy entitlements, compare tiers, or flag anything you're missing.",
    chips: ["What am I entitled to?", 'Explain lump sum vs. actuals', 'Any exceptions I can request?'],
  },
  '/marketplace': {
    context: "I can recommend vendors for your corridor, compare options, or check reviews.",
    chips: ['Best housing vendors for Paris?', 'Compare visa services', 'Who handles school search?'],
  },
  '/inbox': {
    context: "I can summarise threads, draft replies, or flag messages that need action.",
    chips: ['Summarise unread threads', 'Draft a reply', 'What needs my response?'],
  },
  '/cases': {
    context: "I can give you an overview of cases, surface blockers, or generate a status report.",
    chips: ['Which cases are blocked?', 'Cases due this week', 'Generate status report'],
  },
  '/profile': {
    context: "I can help you update your profile, understand role permissions, or check your tier.",
    chips: ['What permissions do I have?', 'How do I update my details?'],
  },
};

function getRouteContext(route: string): RouteContext {
  // Exact match
  if (ROUTE_AI_CONTEXT[route]) return ROUTE_AI_CONTEXT[route];
  // Prefix match (e.g. /cases/abc/roadmap → /roadmap)
  for (const [key, val] of Object.entries(ROUTE_AI_CONTEXT)) {
    if (route.endsWith(key) || route.includes(key + '/')) return val;
  }
  return {
    context: 'I can help you navigate the platform, answer questions, or explain any feature.',
    chips: ['What can I do here?', 'Show me the quick actions', 'How does this work?'],
  };
}

// ─── Claude API helper ────────────────────────────────────────────────────────

declare global {
  interface Window {
    claude?: {
      complete: (prompt: string, options?: { onChunk?: (chunk: string) => void }) => Promise<string>;
    };
  }
}

/**
 * Call the backend /api/ai/chat endpoint with SSE streaming.
 * Parses `data: <chunk>\n\n` lines and forwards each chunk via onChunk.
 * Falls back to dev simulation if the fetch fails or in dev mode.
 */
async function callClaudeAPI(
  prompt: string,
  context: string,
  history: { role: 'user' | 'assistant'; content: string }[],
  onChunk: (chunk: string) => void,
  signal: AbortSignal
): Promise<string> {
  const messages = [...history, { role: 'user' as const, content: prompt }];

  let response: Response;
  try {
    response = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, context, model: CLAUDE_MODEL }),
      signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch {
    // Network error or dev mode — fall back to simulation
    return devSimulate(prompt, context, onChunk, signal);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let accumulated = '';
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done || signal.aborted) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    // Keep the last (possibly incomplete) line in the buffer
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const chunk = line.slice(6);
        if (chunk === '[DONE]') break;
        accumulated += chunk;
        onChunk(chunk);
      }
    }
  }

  return accumulated;
}

/** Dev-mode streaming simulation with a canned reply. */
async function devSimulate(
  prompt: string,
  contextHint: string,
  onChunk: (chunk: string) => void,
  signal: AbortSignal
): Promise<string> {
  const devReply =
    `Thanks for your question about "${prompt.slice(0, 60)}${prompt.length > 60 ? '…' : ''}". ` +
    `I'm your AI assistant powered by Claude. In production this connects to the Claude API. ` +
    `Context: ${contextHint}`;

  let accumulated = '';
  for (let i = 0; i < devReply.length; i++) {
    if (signal.aborted) break;
    await new Promise(r => setTimeout(r, 18));
    const char = devReply[i];
    if (char === undefined) break; // bounded by devReply.length
    accumulated += char;
    onChunk(char);
  }
  return accumulated;
}

/**
 * Stream a response to the given prompt.
 * Calls the real Claude API via callClaudeAPI; uses dev simulation in dev mode
 * or when the API is unavailable.
 */
async function streamResponse(
  prompt: string,
  contextHint: string,
  history: { role: 'user' | 'assistant'; content: string }[],
  onChunk: (chunk: string) => void,
  signal: AbortSignal
): Promise<{ result: string; usedRealApi: boolean }> {
  if (import.meta.env.DEV) {
    const result = await devSimulate(prompt, contextHint, onChunk, signal);
    return { result, usedRealApi: false };
  }
  const result = await callClaudeAPI(prompt, contextHint, history, onChunk, signal);
  return { result, usedRealApi: true };
}

// ─── TypingIndicator ──────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', gap: '4px', alignItems: 'center', padding: '4px 0' }}>
      {[0, 1, 2].map(i => (
        <span
          key={i}
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: 'var(--text-tertiary)',
            animation: `rp-ai-dot 1.2s ease-in-out ${i * 0.2}s infinite`,
            display: 'inline-block',
          }}
        />
      ))}
    </div>
  );
}

// ─── MessageBubble ────────────────────────────────────────────────────────────

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        gap: '4px',
      }}
    >
      <div
        style={{
          maxWidth: '85%',
          padding: '10px 12px',
          borderRadius: isUser
            ? 'var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg)'
            : 'var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm)',
          background: isUser ? 'var(--surface-ai-user-bubble, var(--accent-soft))' : 'var(--surface-ai-assistant-bubble, var(--surface-hover))',
          color: 'var(--text-primary)',
          fontSize: '13px',
          lineHeight: 1.55,
          wordBreak: 'break-word',
          whiteSpace: 'pre-wrap',
        }}
      >
        {message.content || (message.streaming ? <TypingIndicator /> : null)}
        {message.streaming && message.content && (
          <span
            aria-hidden="true"
            style={{
              display: 'inline-block',
              width: '2px',
              height: '13px',
              background: 'var(--text-primary)',
              marginLeft: '2px',
              verticalAlign: 'text-bottom',
              animation: 'rp-blink 0.8s step-end infinite',
            }}
          />
        )}
      </div>
      <time
        dateTime={message.createdAt.toISOString()}
        style={{ fontSize: '11px', color: 'var(--text-tertiary)', padding: '0 2px' }}
      >
        {message.createdAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      </time>
    </div>
  );
}

// ─── AIPanel ──────────────────────────────────────────────────────────────────

export function AIPanel({ open, route, onClose }: AIPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [chipsVisible, setChipsVisible] = useState(true);
  const [usingRealApi, setUsingRealApi] = useState(!import.meta.env.DEV);

  const listRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const routeCtx = getRouteContext(route);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Focus textarea when opened
  useEffect(() => {
    if (open) setTimeout(() => textareaRef.current?.focus(), 150);
  }, [open]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  // Auto-resize textarea
  const resizeTextarea = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    const lineH = 20;
    const maxH = lineH * 4 + 16;
    ta.style.height = Math.min(ta.scrollHeight, maxH) + 'px';
  }, []);

  // Reset chips when route changes
  useEffect(() => {
    setChipsVisible(true);
  }, [route]);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setChipsVisible(false);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Add user message
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      createdAt: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);

    // Add placeholder AI message (streaming)
    const aiMsgId = crypto.randomUUID();
    const aiMsg: ChatMessage = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      createdAt: new Date(),
      streaming: true,
    };
    setMessages(prev => [...prev, aiMsg]);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      // Build history from messages excluding the new placeholder assistant message
      const history = messages
        .filter(m => !m.streaming)
        .map(m => ({ role: m.role, content: m.content }));

      const { usedRealApi } = await streamResponse(
        trimmed,
        routeCtx.context,
        history,
        chunk => {
          setMessages(prev =>
            prev.map(m =>
              m.id === aiMsgId ? { ...m, content: m.content + chunk } : m
            )
          );
        },
        controller.signal
      );
      setUsingRealApi(usedRealApi);
    } finally {
      setMessages(prev =>
        prev.map(m => (m.id === aiMsgId ? { ...m, streaming: false } : m))
      );
      setLoading(false);
      abortRef.current = null;
    }
  }, [loading, messages, routeCtx.context]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        void sendMessage(input);
      }
    },
    [input, sendMessage]
  );

  const clearConversation = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setChipsVisible(true);
    setLoading(false);
  }, []);

  return (
    <>
      {/* Keyframe styles */}
      <style>{`
        @keyframes rp-ai-dot {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1); }
        }
        @keyframes rp-blink {
          50% { opacity: 0; }
        }
        @keyframes rp-panel-in {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `}</style>

      {/* Panel */}
      <aside
        aria-label="AI Assistant"
        aria-hidden={!open}
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: 'var(--ai-panel-w)',
          background: 'var(--surface-ai-panel, var(--surface))',
          borderLeft: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 'var(--z-ai-panel)' as never,
          transform: open ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform var(--transition-base)',
          willChange: 'transform',
        }}
      >
        {/* ── Header ── */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--spacing-2)',
            padding: '0 var(--spacing-3)',
            height: 'var(--topbar-h)',
            borderBottom: '1px solid var(--border-subtle)',
            flexShrink: 0,
          }}
        >
          {/* Sparkles */}
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
            <path d="M5 3v4" /><path d="M19 17v4" /><path d="M3 5h4" /><path d="M17 19h4" />
          </svg>

          <span style={{ flex: 1, fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
            AI Assistant
          </span>

          {/* Model tag */}
          <span
            style={{
              fontSize: '10px',
              color: usingRealApi ? 'var(--text-tertiary)' : 'var(--text-tertiary)',
              background: usingRealApi ? 'var(--surface-hover)' : 'var(--accent-soft)',
              padding: '2px 6px',
              borderRadius: 'var(--radius-full)',
              fontFamily: 'var(--font-mono)',
              flexShrink: 0,
            }}
          >
            {usingRealApi ? CLAUDE_MODEL : 'dev mode'}
          </span>

          {/* Close */}
          <Button unstyled
            onClick={onClose}
            aria-label="Close AI Assistant"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '28px',
              height: '28px',
              borderRadius: 'var(--radius-md)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-tertiary)',
              flexShrink: 0,
              transition: 'background var(--transition-fast), color var(--transition-fast)',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)';
              (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.background = 'none';
              (e.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)';
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </Button>
        </div>

        {/* ── Context strip ── */}
        <div
          style={{
            padding: 'var(--spacing-2) var(--spacing-3)',
            background: 'var(--surface-ai-context-strip, var(--accent-soft))',
            borderBottom: '1px solid var(--border-subtle)',
            flexShrink: 0,
          }}
        >
          <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
            {routeCtx.context}
          </p>
        </div>

        {/* ── Message list ── */}
        <div
          ref={listRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: 'var(--spacing-3)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--spacing-3)',
          }}
        >
          {messages.length === 0 && (
            <p
              style={{
                textAlign: 'center',
                fontSize: '13px',
                color: 'var(--text-tertiary)',
                margin: 'auto 0',
                padding: 'var(--spacing-6) 0',
              }}
            >
              Ask me anything about this page
            </p>
          )}
          {messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
        </div>

        {/* ── Suggested prompts ── */}
        {chipsVisible && messages.length === 0 && (
          <div
            style={{
              padding: '0 var(--spacing-3) var(--spacing-2)',
              display: 'flex',
              flexWrap: 'wrap',
              gap: 'var(--spacing-1)',
              flexShrink: 0,
            }}
          >
            {routeCtx.chips.map(chip => (
              <Button unstyled
                key={chip}
                onClick={() => sendMessage(chip)}
                style={{
                  padding: '5px 10px',
                  borderRadius: 'var(--radius-full)',
                  background: 'var(--surface-hover)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-secondary)',
                  fontSize: '12px',
                  cursor: 'pointer',
                  transition: 'background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast)',
                  whiteSpace: 'nowrap',
                }}
                onMouseEnter={e => {
                  const el = e.currentTarget as HTMLElement;
                  el.style.background = 'var(--accent-soft)';
                  el.style.borderColor = 'var(--accent-border)';
                  el.style.color = 'var(--accent)';
                }}
                onMouseLeave={e => {
                  const el = e.currentTarget as HTMLElement;
                  el.style.background = 'var(--surface-hover)';
                  el.style.borderColor = 'var(--border-subtle)';
                  el.style.color = 'var(--text-secondary)';
                }}
              >
                {chip}
              </Button>
            ))}
          </div>
        )}

        {/* ── Input area ── */}
        <div
          style={{
            padding: 'var(--spacing-2) var(--spacing-3) var(--spacing-3)',
            borderTop: '1px solid var(--border-subtle)',
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--spacing-2)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-end',
              gap: 'var(--spacing-2)',
              background: 'var(--surface-hover)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              padding: 'var(--spacing-2)',
              transition: 'border-color var(--transition-fast)',
            }}
            onFocusCapture={e => {
              (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent-border)';
            }}
            onBlurCapture={e => {
              (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-subtle)';
            }}
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => { setInput(e.target.value); resizeTextarea(); }}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything… (Enter to send)"
              rows={1}
              disabled={loading}
              aria-label="Message input"
              style={{
                flex: 1,
                background: 'none',
                border: 'none',
                outline: 'none',
                resize: 'none',
                fontSize: '13px',
                color: 'var(--text-primary)',
                lineHeight: '20px',
                fontFamily: 'var(--font-sans)',
                maxHeight: '96px',
                overflowY: 'auto',
              }}
            />
            <Button unstyled
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || loading}
              aria-label="Send message"
              style={{
                width: '28px',
                height: '28px',
                borderRadius: 'var(--radius-md)',
                background: input.trim() && !loading ? 'var(--accent)' : 'var(--border-subtle)',
                border: 'none',
                cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: input.trim() && !loading ? '#fff' : 'var(--text-tertiary)',
                flexShrink: 0,
                transition: 'background var(--transition-fast)',
              }}
            >
              {/* ArrowUp icon */}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="12" y1="19" x2="12" y2="5" />
                <polyline points="5 12 12 5 19 12" />
              </svg>
            </Button>
          </div>

          {/* Clear conversation */}
          {messages.length > 0 && (
            <Button unstyled
              onClick={clearConversation}
              style={{
                alignSelf: 'center',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '11px',
                color: 'var(--text-tertiary)',
                padding: '2px 4px',
                borderRadius: 'var(--radius-sm)',
                transition: 'color var(--transition-fast)',
              }}
              onMouseEnter={e => ((e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)')}
              onMouseLeave={e => ((e.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)')}
            >
              Clear conversation
            </Button>
          )}
        </div>
      </aside>
    </>
  );
}

export default AIPanel;
