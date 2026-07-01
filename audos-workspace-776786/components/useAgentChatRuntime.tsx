/**
 * AgentChat runtime hook (PLATFORM-MANAGED).
 *
 * This file is force-copied from genesis-space into every workspace on every
 * recompile. DO NOT edit it per-space — your changes will be overwritten. To
 * restyle the agent element, edit `components/AgentChatView.tsx` instead.
 *
 * Owns: history loading, SSE streaming, WebSocket subscription, tool-use
 * parsing, booster-message filtering, attachment upload, beacon intake,
 * greeting/welcome injection, send/draft state.
 */
import { useState, useEffect, useRef } from 'react';
import { flushSync } from 'react-dom';
import { useSpaceRuntime } from '../SpaceRuntimeContext';

// Module-level guard to prevent duplicate mounts from sending messages
// This persists across component instances to handle React Strict Mode and accidental double-mounts
let globalSendingLock = false;
let lastSendTimestamp = 0;

export interface MessageContent {
  type: 'text' | 'tool_use';
  text?: string;
  name?: string;
  input?: any;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string | MessageContent[];
  attachments?: AttachmentMeta[];
}

export interface AttachmentMeta {
  id: string;
  url: string;
  contentType: string;
  originalName: string;
}

export interface BeaconIntakeResult {
  headline: string;
  reflection: string;
  anchor: string;
  nextSteps: string[];
  starterPrompts: string[];
}

export interface FileAccessLog {
  timestamp: number;
  path: string;
  action: 'read' | 'write';
  tool: string;
}

export interface AgentChatRuntimeProps {
  spaceId: string;
  onFileAccess?: (log: FileAccessLog) => void;
  pendingMessage?: string | null;
  onPendingMessageConsumed?: () => void;
}

export const BEACON_SPACE_IDS = new Set(['workspace-193216']);
export const BEACON_STARTER_PROMPTS = [
  'I need help before a hard conversation.',
  'A conversation just went badly and I need to process it.',
  "They asked me for money and I don't know what to say.",
];

function getStoredBeaconIntake(spaceId: string): BeaconIntakeResult | null {
  try {
    const sessionKey = `space_session_${spaceId}`;
    const stored =
      localStorage.getItem(sessionKey) || sessionStorage.getItem(sessionKey);

    if (!stored || !stored.startsWith('{')) {
      return null;
    }

    const session = JSON.parse(stored);
    const intake = session?.intake?.result;

    if (
      intake &&
      typeof intake.headline === 'string' &&
      typeof intake.reflection === 'string' &&
      typeof intake.anchor === 'string' &&
      Array.isArray(intake.nextSteps) &&
      Array.isArray(intake.starterPrompts)
    ) {
      return intake as BeaconIntakeResult;
    }
  } catch (error) {
    console.error('[AgentChat] Failed to read Beacon intake state:', error);
  }

  return null;
}

// Generate unique instance ID for debugging
let instanceCounter = 0;

// localStorage key for tracking whether a welcome message has already been
// shown for a given (spaceId, sessionId). Welcome messages are injected
// client-side and never persisted server-side, so without this flag they
// re-inject on every mount/revisit.
function welcomeShownKey(spaceId: string, sid: string): string {
  return `agentchat_welcome_shown_${spaceId}_${sid}`;
}

function hasWelcomeBeenShown(spaceId: string, sid: string | undefined): boolean {
  if (!sid) return false;
  try {
    return localStorage.getItem(welcomeShownKey(spaceId, sid)) === 'true';
  } catch {
    return false;
  }
}

function markWelcomeShown(spaceId: string, sid: string | undefined): void {
  if (!sid) return;
  try {
    localStorage.setItem(welcomeShownKey(spaceId, sid), 'true');
  } catch {
    // localStorage unavailable (private mode, quota); fall through silently
  }
}

function getNonEmptyString(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

interface InlineAgentConfig {
  welcomeMessage: string | null;
  greetingPrompt: string | null;
  greetingAutoSend: boolean;
  agentName: string | null;
  thinkingText: string | null;
  hasConversationConfig: boolean;
}

function getInlineAgentConfig(): InlineAgentConfig {
  if (typeof window === 'undefined') {
    return {
      welcomeMessage: null,
      greetingPrompt: null,
      greetingAutoSend: false,
      agentName: null,
      thinkingText: null,
      hasConversationConfig: false,
    };
  }

  const inlineConfig = (window as any).__SPACE_CONFIG__;
  if (!inlineConfig || typeof inlineConfig !== 'object') {
    return {
      welcomeMessage: null,
      greetingPrompt: null,
      greetingAutoSend: false,
      agentName: null,
      thinkingText: null,
      hasConversationConfig: false,
    };
  }

  const rootConfig = inlineConfig as Record<string, unknown>;
  const agentConfig =
    rootConfig.agent && typeof rootConfig.agent === 'object'
      ? (rootConfig.agent as Record<string, unknown>)
      : null;

  const welcomeMessage = getNonEmptyString(agentConfig?.welcomeMessage);
  const greetingPrompt = getNonEmptyString(agentConfig?.greetingPrompt);
  const greetingAutoSend = agentConfig?.greetingAutoSend === true;
  const agentName =
    getNonEmptyString(agentConfig?.name) || getNonEmptyString(rootConfig.name);
  const thinkingText = getNonEmptyString(agentConfig?.thinkingText);

  return {
    welcomeMessage,
    greetingPrompt,
    greetingAutoSend,
    agentName,
    thinkingText,
    hasConversationConfig: Boolean(welcomeMessage || greetingPrompt),
  };
}

export interface AgentChatRuntime {
  spaceId: string;

  // Conversation state
  messages: ChatMessage[];
  streamingContent: string;
  isStreaming: boolean;
  loading: boolean;
  lastAction: string | undefined;
  isLoadingHistory: boolean;
  hasLoadedHistory: boolean;

  // Composer state
  input: string;
  setInput: (value: string) => void;
  pendingAttachments: AttachmentMeta[];
  isUploadingAttachment: boolean;
  isDraggingOver: boolean;

  // Refs the view binds onto DOM nodes
  messagesEndRef: React.RefObject<HTMLDivElement>;
  textareaRef: React.RefObject<HTMLTextAreaElement>;
  fileInputRef: React.RefObject<HTMLInputElement>;
  dropZoneRef: React.RefObject<HTMLDivElement>;

  // Actions
  abortStream: () => void;
  sendMessage: () => Promise<void>;
  sendMessageWithContent: (
    content: string,
    attachments: AttachmentMeta[],
  ) => Promise<void>;
  removeAttachment: (id: string) => void;
  handleFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  handleDragOver: (e: React.DragEvent) => void;
  handleDragLeave: (e: React.DragEvent) => void;
  handleDrop: (e: React.DragEvent) => Promise<void>;
  handlePaste: (e: React.ClipboardEvent) => Promise<void>;
  handleKeyDown: (e: React.KeyboardEvent) => void;

  // Config-derived
  configWelcomeMessage: string | null;
  greetingPrompt: string | null;
  isConfigLoaded: boolean;
  greetingSent: boolean;
  welcomeInjectedSource: 'config' | 'session' | 'fallback' | null;

  // Space-specific
  isBeaconSpace: boolean;
  agentLabel: string;
  thinkingText: string | null;
  beaconIntake: BeaconIntakeResult | null;
  beaconStarterPrompts: string[];
  shortcutPrefix: string;
}

export function useAgentChatRuntime(
  props: AgentChatRuntimeProps,
): AgentChatRuntime {
  const { spaceId, onFileAccess, pendingMessage, onPendingMessageConsumed } = props;

  const { sessionId, trackEvent } = useSpaceRuntime();
  const inlineAgentConfig = getInlineAgentConfig();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [lastAction, setLastAction] = useState<string | undefined>();
  const [pendingAttachments, setPendingAttachments] = useState<AttachmentMeta[]>([]);
  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [hasLoadedHistory, setHasLoadedHistory] = useState(false);
  const [workspaceSessionId, setWorkspaceSessionId] = useState<string | undefined>();
  const [configWelcomeMessage, setConfigWelcomeMessage] = useState<string | null>(
    inlineAgentConfig.welcomeMessage,
  );
  const [sessionWelcomeMessage, setSessionWelcomeMessage] = useState<string | null>(null);
  const [greetingPrompt, setGreetingPrompt] = useState<string | null>(
    inlineAgentConfig.greetingPrompt,
  );
  const [greetingAutoSend, setGreetingAutoSend] = useState<boolean>(
    inlineAgentConfig.greetingAutoSend,
  );
  const [isConfigLoaded, setIsConfigLoaded] = useState(
    inlineAgentConfig.hasConversationConfig,
  );
  const [beaconIntake, setBeaconIntake] = useState<BeaconIntakeResult | null>(null);
  const [configAgentName, setConfigAgentName] = useState<string | null>(
    inlineAgentConfig.agentName,
  );
  const [configThinkingText, setConfigThinkingText] = useState<string | null>(
    inlineAgentConfig.thinkingText,
  );

  // State mirrors of internal guard refs so the view can react to them.
  const [welcomeInjectedSource, setWelcomeInjectedSource] =
    useState<'config' | 'session' | 'fallback' | null>(null);
  const [greetingSent, setGreetingSent] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropZoneRef = useRef<HTMLDivElement>(null);
  const pendingMessageProcessed = useRef(false);
  const isSendingRef = useRef(false);
  const welcomeInjectedSourceRef = useRef<'config' | 'session' | 'fallback' | null>(null);
  const greetingSentRef = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);
  const sseMessageIdsRef = useRef<Set<string>>(new Set());
  const isSSEActiveRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const instanceId = useRef(++instanceCounter);
  const isBeaconSpace = BEACON_SPACE_IDS.has(spaceId);
  const effectiveAgentName = configAgentName || inlineAgentConfig.agentName;
  const effectiveThinkingText = configThinkingText || inlineAgentConfig.thinkingText;
  const agentLabel = effectiveAgentName || (isBeaconSpace ? 'Beacon' : 'Agent');

  const markWelcomeInjected = (source: 'config' | 'session' | 'fallback') => {
    welcomeInjectedSourceRef.current = source;
    setWelcomeInjectedSource(source);
  };

  const markGreetingSent = () => {
    greetingSentRef.current = true;
    setGreetingSent(true);
  };

  // Debug: Log mount/unmount
  useEffect(() => {
    console.log(`[AgentChat] Instance ${instanceId.current} MOUNTED for spaceId: ${spaceId}`);
    return () => {
      console.log(`[AgentChat] Instance ${instanceId.current} UNMOUNTED`);
    };
  }, [spaceId]);

  useEffect(() => {
    const initialInlineAgentConfig = getInlineAgentConfig();
    setSessionWelcomeMessage(null);
    setConfigWelcomeMessage(initialInlineAgentConfig.welcomeMessage);
    setGreetingPrompt(initialInlineAgentConfig.greetingPrompt);
    setGreetingAutoSend(initialInlineAgentConfig.greetingAutoSend);
    setIsConfigLoaded(initialInlineAgentConfig.hasConversationConfig);
    setConfigAgentName(initialInlineAgentConfig.agentName);
    setConfigThinkingText(initialInlineAgentConfig.thinkingText);
    welcomeInjectedSourceRef.current = null;
    setWelcomeInjectedSource(null);
    greetingSentRef.current = false;
    setGreetingSent(false);

    let cancelled = false;
    const loadAgentConfig = async () => {
      let sawInlineGreeting = Boolean(initialInlineAgentConfig.greetingPrompt);
      let sawInlineWelcome = Boolean(initialInlineAgentConfig.welcomeMessage);
      try {
        if (!cancelled) {
          if (initialInlineAgentConfig.welcomeMessage) {
            console.log('[AgentChat] Loaded welcome message from inline config');
          }
          if (initialInlineAgentConfig.greetingPrompt) {
            console.log('[AgentChat] Loaded greeting prompt from inline config');
          }
          if (sawInlineGreeting || sawInlineWelcome) {
            setIsConfigLoaded(true);
          }
        }

        const res = await fetch(`/api/space/${spaceId}/file/config.json`);
        if (cancelled) return;
        if (res.ok) {
          const data = await res.json();
          const config = JSON.parse(data.content);
          if (config?.agent?.welcomeMessage) {
            setConfigWelcomeMessage(config.agent.welcomeMessage);
            if (!sawInlineWelcome) console.log('[AgentChat] Loaded welcome message from config');
          }
          if (config?.agent?.greetingPrompt) {
            setGreetingPrompt(config.agent.greetingPrompt);
            if (!sawInlineGreeting) console.log('[AgentChat] Loaded greeting prompt from config');
          }
          if (config?.agent?.greetingAutoSend === true) {
            setGreetingAutoSend(true);
          }
          if (config?.agent?.name) {
            setConfigAgentName(config.agent.name);
          } else if (config?.name) {
            setConfigAgentName(config.name);
          }
          if (config?.agent?.thinkingText) {
            setConfigThinkingText(config.agent.thinkingText);
          }
        } else {
          console.warn(
            `[AgentChat] Config fetch unavailable (${res.status}) — trying public agent-config endpoint`,
          );
          try {
            const pubRes = await fetch(`/api/space/${spaceId}/agent-config`);
            if (cancelled) return;
            if (pubRes.ok) {
              const pubData = await pubRes.json();
              if (pubData?.agent?.welcomeMessage) {
                setConfigWelcomeMessage(pubData.agent.welcomeMessage);
              }
              if (pubData?.agent?.greetingPrompt) {
                setGreetingPrompt(pubData.agent.greetingPrompt);
              }
              if (pubData?.agent?.greetingAutoSend === true) {
                setGreetingAutoSend(true);
              }
              if (pubData?.agent?.name) {
                setConfigAgentName(pubData.agent.name);
              } else if (pubData?.name) {
                setConfigAgentName(pubData.name);
              }
              if (pubData?.agent?.thinkingText) {
                setConfigThinkingText(pubData.agent.thinkingText);
              }
              console.log('[AgentChat] Loaded agent config from public endpoint');
            }
          } catch {
            // Public endpoint also failed — rely on inline config
          }
        }
      } catch (e) {
        console.error('[AgentChat] Failed to load agent config:', e);
      } finally {
        if (!cancelled) setIsConfigLoaded(true);
      }
    };
    loadAgentConfig();
    return () => {
      cancelled = true;
    };
  }, [spaceId]);

  useEffect(() => {
    const handleSessionReady = (event: CustomEvent) => {
      if (event.detail?.welcomeMessage) {
        console.log('[AgentChat] Received session welcome message from agentSessionReady event');
        setSessionWelcomeMessage(event.detail.welcomeMessage);
      }
    };

    window.addEventListener('agentSessionReady', handleSessionReady as EventListener);

    return () => {
      window.removeEventListener('agentSessionReady', handleSessionReady as EventListener);
    };
  }, []);

  useEffect(() => {
    if (!isBeaconSpace) {
      setBeaconIntake(null);
      return;
    }
    setBeaconIntake(getStoredBeaconIntake(spaceId));
  }, [isBeaconSpace, spaceId, sessionId]);

  const getSessionEmail = () => {
    try {
      const sessionKey = `space_session_${spaceId}`;
      const stored = localStorage.getItem(sessionKey);
      if (stored && stored.startsWith('{')) {
        const session = JSON.parse(stored);
        return session.email || null;
      }
    } catch (e) {
      console.error('[AgentChat] Failed to get session email:', e);
    }
    return null;
  };

  const getStoredWorkspaceSessionId = () => {
    try {
      const sessionKey = `space_session_${spaceId}`;
      const stored = localStorage.getItem(sessionKey);
      if (stored && stored.startsWith('{')) {
        const session = JSON.parse(stored);
        return session.workspaceSessionId || null;
      }
    } catch (e) {
      console.error('[AgentChat] Failed to get stored workspaceSessionId:', e);
    }
    return null;
  };

  // Load chat history when component mounts (if user has email session)
  useEffect(() => {
    const loadHistory = async () => {
      const params = new URLSearchParams();
      params.set('contextType', 'space');

      const effectiveSessionId =
        sessionId && (sessionId.startsWith('wses_') || sessionId.startsWith('guest_')) ? sessionId : getStoredWorkspaceSessionId();

      if (effectiveSessionId) {
        params.set('sessionId', effectiveSessionId);
        console.log('[AgentChat] Using sessionId for history lookup:', effectiveSessionId);
        setWorkspaceSessionId(effectiveSessionId);
      }

      const email = getSessionEmail();
      if (email) {
        params.set('email', email);
      }

      if (!effectiveSessionId && !email) {
        console.log('[AgentChat] No session or email, skipping history load');
        setIsLoadingHistory(false);
        setHasLoadedHistory(true);
        return;
      }

      try {
        console.log('[AgentChat] Loading chat history with params:', params.toString());
        const response = await fetch(
          `/api/space/${spaceId}/chat/history?${params.toString()}`,
        );

        if (response.ok) {
          const data = await response.json();
          console.log('[AgentChat] History response:', data);

          if (data.workspaceSessionId && !effectiveSessionId) {
            console.log(
              '[AgentChat] workspace_session.id for WebSocket subscription:',
              data.workspaceSessionId,
            );
            setWorkspaceSessionId(data.workspaceSessionId);
          } else if (effectiveSessionId) {
            console.log('[AgentChat] Keeping sessionId:', effectiveSessionId);
          } else {
            console.warn('[AgentChat] No workspaceSessionId returned from history endpoint');
          }

          if (data.messages && Array.isArray(data.messages) && data.messages.length > 0) {
            const transformedMessages: ChatMessage[] = [];
            for (const msg of data.messages) {
              if (!msg || typeof msg !== 'object') continue;
              const role = msg.role as 'user' | 'assistant';

              if (role === 'user') {
                transformedMessages.push({
                  role,
                  content: typeof msg.content === 'string' ? msg.content : (msg.content ?? ''),
                });
              } else {
                let content: string | MessageContent[] = msg.content ?? '';

                let events: any[] | null = null;
                if (Array.isArray(content)) {
                  events = content;
                } else if (typeof content === 'string' && content.startsWith('[')) {
                  try {
                    events = JSON.parse(content);
                  } catch (e) {
                    // Not valid JSON, keep as string
                  }
                }

                if (events && Array.isArray(events)) {
                  try {
                    let extractedText = '';

                    const textChunks = events
                      .filter((e: any) => e.type === 'text_chunk' && e.data?.text)
                      .map((e: any) => e.data.text)
                      .join('');

                    if (textChunks) {
                      extractedText = textChunks;
                    }

                    if (!extractedText) {
                      const deltaChunks = events
                        .filter(
                          (e: any) => e.type === 'content_block_delta' && e.data?.delta?.text,
                        )
                        .map((e: any) => e.data.delta.text)
                        .join('');
                      if (deltaChunks) {
                        extractedText = deltaChunks;
                      }
                    }

                    if (!extractedText) {
                      const assistantEvent = events.find(
                        (e: any) => e.type === 'assistant' && e.data?.content,
                      );
                      if (assistantEvent?.data?.content) {
                        const textParts = assistantEvent.data.content
                          .filter((c: any) => c.type === 'text')
                          .map((c: any) => c.text)
                          .join('');
                        if (textParts) {
                          extractedText = textParts;
                        }
                      }
                    }

                    if (!extractedText) {
                      const messageEvent = events.find(
                        (e: any) => e.type === 'message' && e.data?.content,
                      );
                      if (messageEvent?.data?.content) {
                        const textParts = messageEvent.data.content
                          .filter((c: any) => c.type === 'text')
                          .map((c: any) => c.text)
                          .join('');
                        if (textParts) {
                          extractedText = textParts;
                        }
                      }
                    }

                    if (!extractedText) {
                      const resultEvent = events.find(
                        (e: any) => e.type === 'result' && typeof e.data?.result === 'string',
                      );
                      if (resultEvent?.data?.result) {
                        extractedText = resultEvent.data.result;
                      }
                    }

                    if (extractedText) {
                      content = extractedText;
                    } else {
                      console.warn(
                        '[AgentChat] Could not extract text from events:',
                        events.map((e: any) => e.type),
                      );
                    }
                  } catch (e) {
                    console.warn('[AgentChat] Failed to parse assistant message JSON:', e);
                  }
                }

                transformedMessages.push({ role, content });
              }
            }

            if (transformedMessages.length > 0) {
              console.log('[AgentChat] Loaded', transformedMessages.length, 'messages from history');
              setMessages(transformedMessages);
            }
          }
        }
      } catch (error) {
        console.error('[AgentChat] Failed to load history:', error);
      } finally {
        setIsLoadingHistory(false);
        setHasLoadedHistory(true);
      }
    };

    loadHistory();
  }, [spaceId, sessionId]);

  useEffect(() => {
    if (!hasLoadedHistory || !isConfigLoaded) return;

    const hasVisibleMessages = messages.some((m) => {
      if (m.role === 'assistant') return true;
      if (m.role === 'user' && typeof m.content === 'string' && m.content.startsWith('[SYSTEM:'))
        return false;
      return m.role === 'user';
    });
    if (hasVisibleMessages) return;

    const welcomeAlreadyShown =
      welcomeInjectedSourceRef.current !== null ||
      hasWelcomeBeenShown(spaceId, workspaceSessionId);

    if (greetingPrompt && greetingAutoSend && !greetingSentRef.current) {
      if (welcomeAlreadyShown) return;
      if (loading || isSendingRef.current) {
        console.log('[AgentChat] Deferring greeting prompt send — waiting for ready state');
        return;
      }
      markGreetingSent();
      console.log('[AgentChat] Auto-sending greeting prompt to generate AI welcome message');
      const systemMessage = `[SYSTEM: ${greetingPrompt}]`;
      sendMessageWithContent(systemMessage, []);
      return;
    }

    if (greetingSentRef.current && !loading && !welcomeInjectedSourceRef.current) {
      const fallbackTimeout = setTimeout(() => {
        if (greetingSentRef.current && !welcomeInjectedSourceRef.current) {
          const hasAnyAssistant = messages.some((m) => m.role === 'assistant');
          if (hasAnyAssistant) return;
          console.warn(
            '[AgentChat] Greeting prompt sent but no assistant reply arrived — injecting fallback welcome',
          );
          markWelcomeInjected('fallback');
          markWelcomeShown(spaceId, workspaceSessionId);
          const fallbackContent = configWelcomeMessage || 'Hello! How can I help you today?';
          setMessages((prev) => {
            const hasUserMessages = prev.some(
              (m) =>
                m.role === 'user' &&
                !(typeof m.content === 'string' && m.content.startsWith('[SYSTEM:')),
            );
            if (hasUserMessages) return prev;
            if (prev.some((m) => m.role === 'assistant')) return prev;
            return [...prev, { role: 'assistant', content: fallbackContent }];
          });
        }
      }, 8000);
      return () => clearTimeout(fallbackTimeout);
    }

    if (greetingSentRef.current) return;

    const currentSource = welcomeInjectedSourceRef.current;

    if (configWelcomeMessage && currentSource !== 'config') {
      if (welcomeAlreadyShown && !currentSource) return;
      if (currentSource) {
        console.log(`[AgentChat] Replacing ${currentSource} welcome with config welcome message`);
      } else {
        console.log('[AgentChat] Injecting welcome message for new user (source: config)');
      }
      markWelcomeInjected('config');
      markWelcomeShown(spaceId, workspaceSessionId);
      setMessages((prev) => {
        const hasUserMessages = prev.some(
          (m) =>
            m.role === 'user' &&
            !(typeof m.content === 'string' && m.content.startsWith('[SYSTEM:')),
        );
        if (hasUserMessages) return prev;
        return [{ role: 'assistant', content: configWelcomeMessage }];
      });
      return;
    }

    if (currentSource === 'config') return;

    if (sessionWelcomeMessage && currentSource !== 'session') {
      if (welcomeAlreadyShown && !currentSource) return;
      if (currentSource === 'fallback') {
        console.log('[AgentChat] Replacing hardcoded fallback with session API welcome message');
      } else {
        console.log('[AgentChat] Injecting welcome message for new user (source: session API)');
      }
      markWelcomeInjected('session');
      markWelcomeShown(spaceId, workspaceSessionId);
      setMessages((prev) => {
        const hasUserMessages = prev.some(
          (m) =>
            m.role === 'user' &&
            !(typeof m.content === 'string' && m.content.startsWith('[SYSTEM:')),
        );
        if (hasUserMessages) return prev;
        if (prev.length === 0 || (prev.length === 1 && prev[0].role === 'assistant')) {
          return [{ role: 'assistant', content: sessionWelcomeMessage }];
        }
        return prev;
      });
      return;
    }

    if (currentSource) return;

    if (greetingPrompt && greetingAutoSend) return;
    if (!isConfigLoaded) return;
    if (welcomeAlreadyShown) return;

    const timeout = setTimeout(() => {
      if (!welcomeInjectedSourceRef.current && !greetingSentRef.current) {
        console.log(
          '[AgentChat] Injecting welcome message for new user (source: hardcoded fallback after timeout)',
        );
        markWelcomeInjected('fallback');
        markWelcomeShown(spaceId, workspaceSessionId);
        setMessages((prev) => {
          if (prev.length > 0) return prev;
          return [{ role: 'assistant', content: 'Hello! How can I help you today?' }];
        });
      }
    }, 1500);

    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    hasLoadedHistory,
    isConfigLoaded,
    configWelcomeMessage,
    sessionWelcomeMessage,
    greetingPrompt,
    greetingAutoSend,
    messages,
    loading,
    workspaceSessionId,
    spaceId,
  ]);

  // Auto-scroll to bottom when messages update — uses scrollTop on the
  // overflow container instead of scrollIntoView to avoid scrolling the
  // outer page on iOS Safari mobile.
  useEffect(() => {
    const el = messagesEndRef.current?.parentElement;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, streamingContent, loading]);

  // WebSocket subscription for real-time messages
  useEffect(() => {
    if (!workspaceSessionId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws?session_chat=${workspaceSessionId}`;

    console.log('[AgentChat] Connecting WebSocket with workspace_session.id:', workspaceSessionId);
    console.log('[AgentChat] WebSocket URL:', wsUrl);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[AgentChat] WebSocket connected successfully');
      console.log('[AgentChat] Subscribed to workspace_session.id:', workspaceSessionId);
    };

    const processedMessageIds = new Set<string>();

    ws.onmessage = (event) => {
      console.log('[AgentChat] WebSocket event received');
      try {
        const data = JSON.parse(event.data);
        console.log('[AgentChat] WebSocket message type:', data.type);

        if (data.type === 'session_message' && data.message) {
          const messageId = data.message.id;

          if (data.message.role === 'assistant' && isSSEActiveRef.current) {
            console.log(
              '[AgentChat] Skipping WS assistant message during active SSE stream:',
              messageId,
            );
            return;
          }

          if (messageId && sseMessageIdsRef.current.has(String(messageId))) {
            console.log('[AgentChat] Skipping WS message already received via SSE:', messageId);
            return;
          }

          if (messageId && processedMessageIds.has(messageId)) {
            console.log('[AgentChat] Skipping duplicate message ID:', messageId);
            return;
          }
          if (messageId) {
            processedMessageIds.add(messageId);
          }

          console.log(
            '[AgentChat] Processing message:',
            messageId,
            'contentType:',
            data.message.contentType,
          );

          let content: string | MessageContent[] = data.message.content ?? '';

          if (data.message.contentType === 'json' && Array.isArray(data.message.content)) {
            console.log(
              '[AgentChat] Processing JSON event array with',
              data.message.content.length,
              'events',
            );
            let extractedText = '';

            const resultEvent = data.message.content.find(
              (e: any) => e.type === 'result' && e.data?.response,
            );
            if (resultEvent?.data?.response) {
              extractedText = resultEvent.data.response;
              console.log(
                '[AgentChat] ✓ Extracted from result.response:',
                extractedText.substring(0, 50) + '...',
              );
            }

            if (!extractedText) {
              const messageEvent = data.message.content.find(
                (e: any) => e.type === 'message' && e.data?.content,
              );
              if (messageEvent?.data?.content) {
                const textParts = messageEvent.data.content
                  .filter((c: any) => c.type === 'text')
                  .map((c: any) => c.text)
                  .join('');
                if (textParts) {
                  extractedText = textParts;
                  console.log(
                    '[AgentChat] ✓ Extracted from message.content:',
                    extractedText.substring(0, 50) + '...',
                  );
                }
              }
            }

            if (!extractedText) {
              const textChunks = data.message.content
                .filter((e: any) => e.type === 'text_chunk' && e.data?.text)
                .map((e: any) => e.data.text);

              if (textChunks.length > 0) {
                extractedText = textChunks.join('');
                console.log(
                  '[AgentChat] ✓ Reconstructed from text_chunks:',
                  extractedText.substring(0, 50) + '...',
                );
              }
            }

            if (extractedText) {
              content = extractedText;
            } else {
              console.warn(
                '[AgentChat] ✗ Could not extract text, event types:',
                data.message.content.map((e: any) => e.type),
              );
              return;
            }
          }

          if (!content || (typeof content === 'string' && !content.trim())) {
            console.log('[AgentChat] Skipping empty content message');
            return;
          }

          const newMessage: ChatMessage = {
            role: data.message.role as 'user' | 'assistant',
            content,
          };

          console.log('[AgentChat] ✓ Adding message to UI, role:', newMessage.role);
          setMessages((prev) => {
            // Content-based dedup: skip if the last message has the same
            // role and identical text (covers SSE→WS race window).
            if (prev.length > 0) {
              const last = prev[prev.length - 1];
              if (last.role === newMessage.role) {
                const lastText = typeof last.content === 'string' ? last.content : '';
                const newText = typeof newMessage.content === 'string' ? newMessage.content : '';
                if (lastText && newText && lastText === newText) {
                  console.log('[AgentChat] Skipping duplicate WS message (content matches last message)');
                  return prev;
                }
              }
            }
            return [...prev, newMessage];
          });
        }
      } catch (e) {
        console.warn('[AgentChat] Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('[AgentChat] WebSocket error:', error);
    };

    ws.onclose = (event) => {
      console.log('[AgentChat] WebSocket disconnected:', event.code, event.reason);
    };

    return () => {
      console.log('[AgentChat] Cleaning up WebSocket connection');
      ws.close(1000, 'Component unmounting');
      wsRef.current = null;
    };
  }, [workspaceSessionId]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const newHeight = Math.min(textarea.scrollHeight, 72);
      textarea.style.height = `${newHeight}px`;
    }
  }, [input]);

  // Load Claude session synchronously on mount using initializer function
  const [claudeSessionId, setClaudeSessionId] = useState<string | undefined>(() => {
    const sessionKey = `claude_session_${spaceId}`;
    return sessionStorage.getItem(sessionKey) || undefined;
  });

  useEffect(() => {
    if (claudeSessionId) {
      const sessionKey = `claude_session_${spaceId}`;
      sessionStorage.setItem(sessionKey, claudeSessionId);
    }
  }, [claudeSessionId, spaceId]);

  // Handle pending message from launcher input
  useEffect(() => {
    if (pendingMessage && !pendingMessageProcessed.current && !loading) {
      pendingMessageProcessed.current = true;
      setInput(pendingMessage);
      setTimeout(() => {
        onPendingMessageConsumed?.();
      }, 100);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingMessage, loading]);

  useEffect(() => {
    if (input && pendingMessageProcessed.current && !loading && hasLoadedHistory) {
      pendingMessageProcessed.current = false;
      sendMessageWithContent(input, []);
      setInput('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input, hasLoadedHistory]);

  // Helper function to upload files (used by file input, drag-drop, and paste)
  const uploadFiles = async (files: File[]) => {
    if (files.length === 0) return;

    if (pendingAttachments.length + files.length > 5) {
      console.warn('[AgentChat] Too many files - max 5 allowed');
      return;
    }

    const supportedFiles = files.filter(
      (file) => file.type.startsWith('image/') || file.type === 'application/pdf',
    );

    if (supportedFiles.length === 0) {
      console.warn('[AgentChat] No supported files found');
      return;
    }

    setIsUploadingAttachment(true);

    try {
      const formData = new FormData();
      supportedFiles.forEach((file) => {
        formData.append('files', file);
      });

      const res = await fetch(`/api/uploads/attachments?configId=${spaceId}`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.error || 'Upload failed');
      }

      const data = await res.json();
      setPendingAttachments((prev) => [...prev, ...data.attachments]);
      console.log(`[AgentChat] Uploaded ${data.attachments.length} files`);
    } catch (error: any) {
      console.error('[AgentChat] Upload failed:', error.message);
    } finally {
      setIsUploadingAttachment(false);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      await uploadFiles(Array.from(files));
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeAttachment = (attachmentId: string) => {
    setPendingAttachments((prev) => prev.filter((a) => a.id !== attachmentId));
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (dropZoneRef.current && !dropZoneRef.current.contains(e.relatedTarget as Node)) {
      setIsDraggingOver(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      await uploadFiles(files);
    }
  };

  const handlePaste = async (e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    const files: File[] = [];

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind === 'file') {
        const file = item.getAsFile();
        if (file && (file.type.startsWith('image/') || file.type === 'application/pdf')) {
          files.push(file);
        }
      }
    }

    if (files.length > 0) {
      e.preventDefault();
      await uploadFiles(files);
    }
  };

  // Core send function that takes message content directly
  const sendMessageWithContent = async (
    messageContent: string,
    attachmentsToSend: AttachmentMeta[],
  ) => {
    if ((!messageContent.trim() && attachmentsToSend.length === 0) || loading) return;

    if (!hasLoadedHistory) {
      console.log('[AgentChat] Waiting for history to load before sending...');
      return;
    }

    if (isSendingRef.current) {
      console.log(`[AgentChat] Ignoring duplicate API call - already sending (ref)`);
      return;
    }

    const now = Date.now();
    const timeSinceLastSend = now - lastSendTimestamp;
    if (timeSinceLastSend < 1000) {
      console.log(`[AgentChat] Ignoring duplicate API call - sent ${timeSinceLastSend}ms ago`);
      return;
    }

    console.log(`[AgentChat] Sending message, acquiring locks`);
    isSendingRef.current = true;
    globalSendingLock = true;
    lastSendTimestamp = now;

    const userMessage: ChatMessage = {
      role: 'user',
      content: messageContent,
      attachments: attachmentsToSend.length > 0 ? attachmentsToSend : undefined,
    };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setLastAction(undefined);

    trackEvent('agent_message', {
      messageLength: messageContent.length,
      messagePreview: messageContent.slice(0, 50),
      attachmentCount: attachmentsToSend.length,
    });

    isSSEActiveRef.current = true;
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      const email = getSessionEmail();
      console.log(
        '[AgentChat] Sending message with email:',
        email,
        'attachments:',
        attachmentsToSend.length,
      );

      const res = await fetch(`/api/space/${spaceId}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: messageContent,
          sessionId: sessionId,
          claudeSessionId: claudeSessionId,
          email: email,
          attachments: attachmentsToSend.length > 0 ? attachmentsToSend : undefined,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('No reader available');

      const decoder = new TextDecoder();
      let buffer = '';
      let chunkCount = 0;
      let totalTextLength = 0;
      let accumulatedText = '';

      console.log('[SPACE-STREAM-DEBUG] Starting to read SSE stream...');

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log(
            '[SPACE-STREAM-DEBUG] Stream ended. Total chunks:',
            chunkCount,
            'Total text length:',
            totalTextLength,
          );
          break;
        }

        const rawChunk = decoder.decode(value, { stream: true });
        console.log('[SPACE-STREAM-DEBUG] Raw chunk received, length:', rawChunk.length, 'bytes');

        buffer += rawChunk;
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              console.log('[SPACE-STREAM-DEBUG] Received [DONE] signal');
              setStreamingContent('');
              continue;
            }

            try {
              const event = JSON.parse(data);
              console.log(
                '[SPACE-STREAM-DEBUG] Event type:',
                event.type,
                'timestamp:',
                event.timestamp,
              );

              if (event.type === 'streaming_message_init' && event.data?.messageId) {
                sseMessageIdsRef.current.add(String(event.data.messageId));
              } else if (event.type === 'text_chunk') {
                chunkCount++;
                const text = event.data?.text || '';
                totalTextLength += text.length;
                accumulatedText += text;
                console.log(
                  '[SPACE-STREAM-DEBUG] text_chunk #' + chunkCount + ':',
                  text.substring(0, 50),
                  '(' + text.length + ' chars)',
                );
                flushSync(() => {
                  setIsStreaming(true);
                  setStreamingContent((prev) => prev + text);
                });
                await new Promise((resolve) => requestAnimationFrame(resolve));
              } else if (event.type === 'message') {
                setIsStreaming(false);
                setStreamingContent('');
                const msgContent = event.data?.content ?? '';
                setMessages((prev) => [...prev, { ...event.data, content: msgContent }]);

                if (Array.isArray(event.data?.content)) {
                  for (const chunk of event.data.content) {
                    if (chunk.type === 'tool_use') {
                      setIsStreaming(false);
                      setStreamingContent('');
                      setLastAction(chunk.name);

                      if (chunk.name === 'read_file' && chunk.input?.file_path) {
                        onFileAccess?.({
                          timestamp: Date.now(),
                          path: chunk.input.file_path,
                          action: 'read',
                          tool: 'read_file',
                        });
                      } else if (chunk.name === 'write_file' && chunk.input?.file_path) {
                        onFileAccess?.({
                          timestamp: Date.now(),
                          path: chunk.input.file_path,
                          action: 'write',
                          tool: 'write_file',
                        });
                      }
                    }
                  }
                }
              } else if (event.type === 'progress') {
                if (event.data?.message) {
                  setIsStreaming(false);
                  setLastAction(event.data.message);
                }
                if (event.data?.sessionId) {
                  setClaudeSessionId(event.data.sessionId);
                }
              } else if (event.type === 'result') {
                setLoading(false);
                setIsStreaming(false);
                setLastAction(undefined);
                if (event.data?.sessionId) {
                  setClaudeSessionId(event.data.sessionId);
                }
              } else if (event.type === 'error') {
                throw new Error(event.data.error);
              }
            } catch (e) {
              console.warn('Failed to parse event:', data);
            }
          }
        }
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        console.log('[AgentChat] Stream aborted by user');
        if (accumulatedText) {
          setMessages((prev) => [...prev, { role: 'assistant', content: accumulatedText }]);
        }
      } else {
        console.error('Chat error:', err);
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `Sorry, I encountered an error. Please try again.`,
          },
        ]);
      }
    } finally {
      setLoading(false);
      setIsStreaming(false);
      setStreamingContent('');
      setLastAction(undefined);
      isSendingRef.current = false;
      globalSendingLock = false;
      abortControllerRef.current = null;
      // Delay clearing isSSEActiveRef so that any WS broadcast of the same
      // assistant turn (sent by the server's finally block) is still
      // suppressed by the WS handler's isSSEActiveRef guard.
      setTimeout(() => {
        isSSEActiveRef.current = false;
      }, 2000);
    }
  };

  const abortStream = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  };

  const sendMessage = async () => {
    if ((!input.trim() && pendingAttachments.length === 0) || loading) return;
    const messageToSend = input;
    const attachmentsToSend = [...pendingAttachments];
    setInput('');
    setPendingAttachments([]);
    await sendMessageWithContent(messageToSend, attachmentsToSend);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !loading) {
      e.preventDefault();
      sendMessage();
    }
  };

  const shortcutPrefix =
    typeof navigator !== 'undefined' && navigator.platform?.includes('Mac') ? '⌘' : 'Ctrl';

  return {
    spaceId,

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

    configWelcomeMessage,
    greetingPrompt: greetingAutoSend ? greetingPrompt : null,
    isConfigLoaded,
    greetingSent,
    welcomeInjectedSource,

    isBeaconSpace,
    agentLabel,
    thinkingText: effectiveThinkingText,
    beaconIntake,
    beaconStarterPrompts: BEACON_STARTER_PROMPTS,
    shortcutPrefix,
  };
}

export default useAgentChatRuntime;
