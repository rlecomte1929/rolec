/**
 * AgentChatView — per-space agent UI.
 *
 * THIS FILE IS THE PER-SPACE AGENT APPEARANCE. Edit it to restyle the agent
 * element (colors, spacing, copy, layout, message bubbles, header card,
 * suggestion chips, empty state, input bar, etc.). Your edits PERSIST across
 * recompiles.
 *
 * The runtime hook `useAgentChatRuntime` and the `AgentChat.tsx` shell are
 * platform-managed and force-overwritten on each compile — do not put any
 * logic / state / fetch / effect work in here. This view is purely
 * presentational; it consumes the runtime and renders.
 */
import {
  Bot,
  Send,
  BookOpen,
  Edit3,
  Save,
  Sparkles,
  Loader2,
  FolderOpen,
  Search,
  ListChecks,
  Paperclip,
  X,
  FileImage,
  File,
  XCircle,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getFriendlyTerm, getToolColor } from '../lib/friendly-terms';
import { tw } from '../lib/colors';
import type { AgentChatRuntime } from './useAgentChatRuntime';

interface AgentChatViewProps {
  runtime: AgentChatRuntime;
}

function WorkingIndicator({
  lastAction,
  agentLabel = 'Agent',
  thinkingText,
}: {
  lastAction?: string;
  agentLabel?: string;
  thinkingText?: string | null;
}) {
  const actionIcons: Record<string, any> = {
    read_file: BookOpen,
    write_file: Save,
    edit_file: Edit3,
    write_task_list: ListChecks,
    glob: Search,
    grep: Search,
    ls: FolderOpen,
  };

  const Icon = actionIcons[lastAction || ''] || Loader2;
  const friendlyText = getFriendlyTerm(lastAction || '', 'thinking');
  const color = getToolColor(lastAction || '');

  return (
    <div className="flex items-center justify-center py-2 mr-8">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-[var(--space-surface-muted)] rounded-full border border-[var(--space-border-default)]">
        <Icon className={`h-4 w-4 ${color} animate-spin`} />
        <span className={`text-xs font-medium ${color}`}>
          {thinkingText || `${agentLabel} is ${friendlyText}...`}
        </span>
      </div>
    </div>
  );
}

// react-markdown strips its internal `node` prop from the rest spread when
// destructured, which keeps it from leaking onto DOM elements.
const SAFE_MARKDOWN_PROTOCOLS = /^(subscribe|app|https?|mailto|tel|ircs?|xmpp):/i;

const markdownUrlTransform = (value: string): string => {
  if (typeof value === 'string' && SAFE_MARKDOWN_PROTOCOLS.test(value)) {
    return value;
  }

  const colon = value.indexOf(':');
  const slash = value.indexOf('/');
  const question = value.indexOf('?');
  const hash = value.indexOf('#');

  if (
    colon === -1 ||
    (slash !== -1 && colon > slash) ||
    (question !== -1 && colon > question) ||
    (hash !== -1 && colon > hash)
  ) {
    return value;
  }

  return '';
};

const markdownComponents: Components = {
  p({ node: _node, children, ...props }) {
    return (
      <p className="my-2 text-base" {...props}>
        {children}
      </p>
    );
  },
  ul({ node: _node, children, ...props }) {
    return (
      <ul
        className="my-3 pl-5 space-y-1"
        style={{ listStyleType: 'disc', listStylePosition: 'outside' }}
        {...props}
      >
        {children}
      </ul>
    );
  },
  ol({ node: _node, children, ...props }) {
    return (
      <ol
        className="my-3 pl-5 space-y-1"
        style={{ listStyleType: 'decimal', listStylePosition: 'outside' }}
        {...props}
      >
        {children}
      </ol>
    );
  },
  li({ node: _node, children, ...props }) {
    return (
      <li className="ml-0 text-base" style={{ display: 'list-item' }} {...props}>
        {children}
      </li>
    );
  },
  table({ node: _node, children, ...props }) {
    return (
      <div className="overflow-x-auto my-3">
        <table
          className="min-w-full border-collapse border border-[var(--space-border-default)] text-sm"
          {...props}
        >
          {children}
        </table>
      </div>
    );
  },
  thead({ node: _node, children, ...props }) {
    return (
      <thead className="bg-[var(--space-surface-muted)]" {...props}>
        {children}
      </thead>
    );
  },
  tbody({ node: _node, children, ...props }) {
    return <tbody {...props}>{children}</tbody>;
  },
  tr({ node: _node, children, ...props }) {
    return (
      <tr className="border-b border-[var(--space-border-default)]" {...props}>
        {children}
      </tr>
    );
  },
  th({ node: _node, children, ...props }) {
    return (
      <th
        className="border border-[var(--space-border-default)] px-3 py-2 text-left font-semibold"
        {...props}
      >
        {children}
      </th>
    );
  },
  td({ node: _node, children, ...props }) {
    return (
      <td className="border border-[var(--space-border-default)] px-3 py-2" {...props}>
        {children}
      </td>
    );
  },
  code({ node: _node, children, className, ...props }) {
    const isBlock = typeof className === 'string' && className.includes('language-');
    if (isBlock) {
      return (
        <code className={`${className ?? ''} break-all`} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code
        className="bg-gray-800 text-gray-100 px-1.5 py-0.5 rounded text-sm break-all"
        {...props}
      >
        {children}
      </code>
    );
  },
  pre({ node: _node, children, ...props }) {
    return (
      <pre
        className="bg-gray-800 text-gray-100 rounded-lg p-3 my-2 overflow-x-auto max-w-full"
        style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}
        {...props}
      >
        {children}
      </pre>
    );
  },
  a({ node: _node, href, children }) {
    if (typeof href === 'string' && href.startsWith('app://')) {
      const appId = href.replace('app://', '');
      return (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('[AgentChat] Button click - opening app:', appId);
            window.dispatchEvent(new CustomEvent('openApp', { detail: { appId } }));
          }}
          className={`inline-flex items-center gap-1 px-3 py-1 ${tw.button.primary} rounded-lg transition-colors text-xs font-medium mx-1`}
          data-testid={`link-app-${appId}`}
        >
          {children}
        </button>
      );
    }
    if (typeof href === 'string' && href.startsWith('subscribe://')) {
      return (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            window.dispatchEvent(new CustomEvent('endIntroSession'));
          }}
          className="text-[var(--space-text-brand)] hover:underline break-all bg-transparent border-none p-0 font-inherit text-left"
          data-testid="link-subscribe-plans"
        >
          {children}
        </button>
      );
    }
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        title={href}
        className="text-[var(--space-text-brand)] hover:text-[var(--space-text-accent)] hover:underline break-all"
      >
        {children}
      </a>
    );
  },
};

export default function AgentChatView({ runtime }: AgentChatViewProps) {
  const {
    messages,
    streamingContent,
    isStreaming,
    loading,
    lastAction,
    isLoadingHistory,
    hasLoadedHistory,
    input,
    setInput,
    pendingAttachments,
    isUploadingAttachment,
    isDraggingOver,
    messagesEndRef,
    textareaRef,
    fileInputRef,
    dropZoneRef,
    abortStream,
    sendMessage,
    sendMessageWithContent,
    removeAttachment,
    handleFileSelect,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handlePaste,
    handleKeyDown,
    greetingPrompt,
    isConfigLoaded,
    greetingSent,
    welcomeInjectedSource,
    isBeaconSpace,
    agentLabel,
    thinkingText,
    beaconIntake,
    beaconStarterPrompts,
    shortcutPrefix,
  } = runtime;

  const hasUserMessages = messages.some((message) => message.role === 'user');
  const shouldShowBeaconIntake = isBeaconSpace && !!beaconIntake && !hasUserMessages;
  const composerPlaceholder = pendingAttachments.length > 0
    ? isBeaconSpace
      ? 'Add any context about these files...'
      : 'Add a message about the files...'
    : isBeaconSpace
      ? shouldShowBeaconIntake
        ? 'We can keep building from your starter plan, or you can tell me what changed...'
        : "Tell me what happened, or what you're worried about..."
      : 'Ask me anything... (paste or drop images here)';

  const visibleMessages = messages.filter(
    (m) => !(m.role === 'user' && typeof m.content === 'string' && m.content.startsWith('[SYSTEM:')),
  );

  const isPending =
    isLoadingHistory ||
    !isConfigLoaded ||
    (!!greetingPrompt && !greetingSent) ||
    (greetingSent && !welcomeInjectedSource);

  const showPendingPlaceholder =
    visibleMessages.length === 0 &&
    !loading &&
    !streamingContent &&
    !shouldShowBeaconIntake &&
    isPending;

  const showEmptyStateWelcome =
    !isLoadingHistory &&
    hasLoadedHistory &&
    isConfigLoaded &&
    visibleMessages.length === 0 &&
    !greetingSent &&
    !greetingPrompt &&
    !shouldShowBeaconIntake;

  return (
    <div
      className={`h-full flex flex-col ${
        isBeaconSpace
          ? 'bg-gradient-to-br from-emerald-50/60 via-stone-50 to-sky-50/30'
          : 'bg-[linear-gradient(135deg,var(--space-surface-gradient-from),var(--space-surface-gradient-via),var(--space-surface-gradient-to))]'
      }`}
    >
      <div className="flex-1 overflow-auto p-6 space-y-4">
        {/* Pending-init placeholder so the user never sees a blank chat */}
        {showPendingPlaceholder && (
          <div className="flex justify-start mr-8">
            <div className="bg-[var(--space-surface-panel)] border border-[var(--space-border-default)] rounded-lg px-4 py-2 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-[var(--space-text-muted)]" />
              <span className="text-xs text-[var(--space-text-secondary)]">Getting ready…</span>
            </div>
          </div>
        )}

        {!isLoadingHistory && hasLoadedHistory && shouldShowBeaconIntake && beaconIntake && (
          <div className="px-4">
            <div className="mx-auto max-w-2xl overflow-hidden rounded-3xl border border-emerald-100 bg-white/90 shadow-sm">
              <div className="border-b border-emerald-100 bg-gradient-to-r from-emerald-50 via-white to-sky-50 px-6 py-5">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700">
                  Your Beacon starting point
                </p>
                <h2 className="mt-2 text-xl font-semibold text-slate-900">
                  {beaconIntake.headline}
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">{beaconIntake.reflection}</p>
              </div>

              <div className="space-y-5 px-6 py-5">
                <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 px-4 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">
                    Today's anchor
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{beaconIntake.anchor}</p>
                </div>

                <div>
                  <p className="text-sm font-semibold text-slate-900">Good next steps</p>
                  <div className="mt-3 space-y-2">
                    {beaconIntake.nextSteps.map((step) => (
                      <div
                        key={step}
                        className="flex items-start gap-3 rounded-2xl bg-stone-50 px-4 py-3 text-sm text-slate-700"
                      >
                        <div className="mt-0.5 h-2 w-2 rounded-full bg-emerald-600" />
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-sm font-semibold text-slate-900">Continue from here</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {beaconIntake.starterPrompts.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        onClick={() => {
                          void sendMessageWithContent(prompt, []);
                        }}
                        className="rounded-full border border-emerald-200 bg-white px-4 py-2 text-sm font-medium text-emerald-900 shadow-sm transition hover:border-emerald-300 hover:bg-emerald-50"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Welcome message - only shown when confirmed no history exists */}
        {showEmptyStateWelcome ? (
          <div className="mt-8 px-4">
            {isBeaconSpace ? (
              <div className="mx-auto max-w-xl rounded-3xl border border-emerald-100 bg-gradient-to-b from-emerald-50 via-white to-white px-6 py-8 text-center shadow-sm">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-700 text-white shadow-sm">
                  <Bot className="h-6 w-6" />
                </div>
                <h2 className="text-xl font-semibold text-slate-900">Start with the hard part</h2>
                <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-600">
                  Tell Beacon what happened, what conversation you are dreading, or what you need help saying next.
                </p>
                <div className="mt-5 flex flex-wrap justify-center gap-2">
                  {beaconStarterPrompts.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => {
                        void sendMessageWithContent(prompt, []);
                      }}
                      className="rounded-full border border-emerald-200 bg-white px-4 py-2 text-sm font-medium text-emerald-900 shadow-sm transition hover:border-emerald-300 hover:bg-emerald-50"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center text-[var(--space-text-secondary)]">
                <Bot className="w-12 h-12 mx-auto mb-3 text-[var(--space-shell-icon)]" />
                <p className="text-sm text-[var(--space-text-primary)]">Ask me anything to get started</p>
              </div>
            )}
          </div>
        ) : (
          visibleMessages.length > 0 &&
          visibleMessages.map((msg, idx) => (
            <div key={idx}>
              <div
                className={`p-3 rounded-lg overflow-hidden min-w-0 ${
                  msg.role === 'user' ? `${tw.message.user} ml-8` : `${tw.message.assistant} mr-8`
                }`}
              >
                <p className="text-sm font-medium mb-1">
                  {isBeaconSpace
                    ? msg.role === 'assistant'
                      ? 'Beacon'
                      : 'You'
                    : msg.role.charAt(0).toUpperCase() + msg.role.slice(1)}
                </p>

                {msg.role === 'user' && msg.attachments && msg.attachments.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    {msg.attachments.map((att) => (
                      <div
                        key={att.id}
                        className="flex items-center gap-1 px-2 py-1 bg-[var(--space-surface-card)]/80 border border-[var(--space-border-default)] rounded text-xs"
                      >
                        {att.contentType.startsWith('image/') ? (
                          <FileImage className="w-3 h-3 text-[var(--space-text-brand)]" />
                        ) : (
                          <File className="w-3 h-3 text-[var(--space-text-muted)]" />
                        )}
                        <span className="max-w-[100px] truncate">{att.originalName}</span>
                      </div>
                    ))}
                  </div>
                )}

                {typeof msg.content === 'string' || msg.content == null ? (
                  <div
                    className={`prose prose-base max-w-none ${
                      msg.role === 'user' ? 'text-base' : 'text-base'
                    }`}
                  >
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={markdownComponents}
                      urlTransform={markdownUrlTransform}
                    >
                      {typeof msg.content === 'string' ? msg.content : ''}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {(Array.isArray(msg.content) ? msg.content : []).map((chunk, chunkIdx) => (
                      <div key={chunkIdx}>
                        {chunk.type === 'text' && chunk.text && (
                          <div className="prose prose-base max-w-none text-base">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={markdownComponents}
                              urlTransform={markdownUrlTransform}
                            >
                              {chunk.text}
                            </ReactMarkdown>
                          </div>
                        )}
                        {chunk.type === 'tool_use' && (
                          <div className="border border-[var(--space-border-default)] rounded-lg overflow-hidden mt-2">
                            <div className="bg-[var(--space-surface-muted)] px-3 py-2 flex items-center gap-2 flex-wrap">
                              {chunk.name === 'edit_file' ? (
                                <Edit3 className="w-3.5 h-3.5 text-[var(--space-text-brand)]" />
                              ) : chunk.name === 'read_file' ? (
                                <BookOpen className="w-3.5 h-3.5 text-[var(--space-text-brand)]" />
                              ) : chunk.name === 'write_file' ? (
                                <Save className="w-3.5 h-3.5 text-[var(--space-semantic-success)]" />
                              ) : (
                                <Sparkles className="w-3.5 h-3.5 text-[var(--space-text-muted)]" />
                              )}
                              <span className="text-xs font-semibold text-[var(--space-text-secondary)]">
                                {chunk.name === 'read_file'
                                  ? 'Viewing'
                                  : chunk.name === 'write_file'
                                    ? 'Creating'
                                    : chunk.name === 'edit_file'
                                      ? 'Updating'
                                      : getFriendlyTerm(chunk.name || '', 'Tool Use')}
                              </span>
                              {chunk.input?.file_path && (
                                <span className="font-mono text-xs text-[var(--space-text-muted)] break-all">
                                  {chunk.input.file_path}
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {loading && !streamingContent && (
          <WorkingIndicator lastAction={lastAction} agentLabel={agentLabel} thinkingText={thinkingText} />
        )}

        {streamingContent && (
          <div
            className={`${isBeaconSpace ? 'bg-white/90 border border-emerald-100 shadow-sm' : `${tw.message.assistant}`} mr-8 p-3 rounded-lg overflow-hidden min-w-0`}
          >
            <p className="text-sm font-medium mb-1 text-[var(--space-text-primary)]">{agentLabel}</p>
            <div className="prose prose-base max-w-none text-base">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
                urlTransform={markdownUrlTransform}
              >
                {streamingContent}
              </ReactMarkdown>
              {isStreaming && (
                <span className="inline-block w-0.5 h-4 ml-1 bg-[var(--space-text-primary)] animate-pulse" />
              )}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="px-3 py-2 border-t border-[var(--space-border-default)] bg-[var(--space-surface-panel)]/95 backdrop-blur-sm">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          accept="image/*,application/pdf"
          multiple
          className="hidden"
          data-testid="input-file-attachment"
        />

        <div
          ref={dropZoneRef}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`rounded-2xl border-2 transition-colors overflow-hidden ${
            isDraggingOver ? 'border-[var(--space-brand-highlight)] bg-[var(--space-surface-accent-soft)]' : 'border-[var(--space-border-default)] bg-[var(--space-surface-muted)]'
          }`}
        >
          {isDraggingOver && (
            <div className="flex items-center justify-center py-3 px-4 bg-[var(--space-surface-accent-soft)] border-b border-[var(--space-border-default)]">
              <FileImage className="w-4 h-4 text-[var(--space-text-accent)] mr-2" />
              <span className="text-sm text-[var(--space-text-accent)] font-medium">Drop files here</span>
            </div>
          )}

          {pendingAttachments.length > 0 && (
            <div className="flex flex-wrap gap-2 px-3 pt-2">
              {pendingAttachments.map((attachment) => (
                <div
                  key={attachment.id}
                  className="relative flex items-center gap-1 px-2 py-1 bg-[var(--space-surface-card)] rounded-lg text-xs border border-[var(--space-border-default)]"
                  data-testid={`attachment-preview-${attachment.id}`}
                >
                  {attachment.contentType.startsWith('image/') ? (
                    <FileImage className="w-3 h-3 text-[var(--space-text-brand)]" />
                  ) : (
                    <File className="w-3 h-3 text-[var(--space-text-muted)]" />
                  )}
                  <span className="max-w-[100px] truncate text-[var(--space-text-secondary)]">
                    {attachment.originalName}
                  </span>
                  <button
                    onClick={() => removeAttachment(attachment.id)}
                    className="ml-1 text-[var(--space-text-muted)] hover:text-red-400"
                    data-testid={`button-remove-attachment-${attachment.id}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={composerPlaceholder}
            className="w-full border-0 bg-transparent px-3 py-2 text-sm text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)] focus:outline-none focus:ring-0 resize-none leading-5"
            rows={1}
            disabled={loading}
            data-testid="textarea-instruction"
          />

          <div className="flex items-center justify-between px-2 pb-1">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={loading || isUploadingAttachment || pendingAttachments.length >= 5}
              className="h-8 w-8 flex items-center justify-center rounded-xl hover:bg-[var(--space-surface-card-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              data-testid="button-attach-file"
              title="Attach files (images, PDFs)"
            >
              {isUploadingAttachment ? (
                <Loader2 className="w-4 h-4 animate-spin text-[var(--space-text-muted)]" />
              ) : (
                <Paperclip className="w-4 h-4 text-[var(--space-text-muted)]" />
              )}
            </button>

            <button
              onClick={loading ? abortStream : sendMessage}
              disabled={(!input.trim() && pendingAttachments.length === 0) && !loading}
              className={`h-8 w-8 flex items-center justify-center rounded-xl transition-colors ${
                loading
                  ? 'bg-red-500 hover:bg-red-600 text-white'
                  : `${tw.button.primary} disabled:opacity-50 disabled:cursor-not-allowed`
              }`}
              data-testid="button-send-message"
            >
              {loading ? <XCircle className="w-4 h-4" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <p className="text-[10px] text-[var(--space-text-muted)] mt-1 text-center leading-tight">
          {shortcutPrefix}+Enter to send
        </p>
      </div>
    </div>
  );
}
