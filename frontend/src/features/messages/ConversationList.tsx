import React, { Fragment } from 'react';
import type { Conversation } from './types';

function formatTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000);
  if (diffDays === 0) {
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return d.toLocaleDateString('en-GB', { weekday: 'short' });
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

function truncate(str: string, max: number): string {
  if (!str) return '';
  return str.length <= max ? str : str.slice(0, max).trimEnd() + '…';
}

export type ConversationListSection = {
  title: string;
  conversations: Conversation[];
  emptyHint?: string;
};

interface ConversationListProps {
  /** Flat list (HR / default). Ignored when `sections` is set. */
  conversations?: Conversation[];
  /** Grouped sections (employee: HR vs suppliers). */
  sections?: ConversationListSection[];
  activeId: string | null;
  onSelect: (id: string) => void;
  /** HR management mode */
  editMode?: boolean;
  selectedAssignmentIds?: Set<string>;
  onToggleSelectAssignment?: (assignmentId: string) => void;
  showArchivedBadge?: boolean;
}

function renderConversationRow(
  conv: Conversation,
  isActive: boolean,
  onSelect: (id: string) => void,
  editMode: boolean,
  selectedAssignmentIds: Set<string> | undefined,
  onToggleSelectAssignment: ((assignmentId: string) => void) | undefined,
  showArchivedBadge: boolean
) {
  const selected = selectedAssignmentIds?.has(conv.assignment_id) ?? false;
  return (
    <div
      key={conv.id}
      className={`
                  flex items-stretch border-b border-[#e2e8f0]/80 transition-colors duration-150
                  ${isActive ? 'bg-[#E8F0FE]' : 'hover:bg-[#F5F7FA]'}
                `}
    >
      {editMode && (
        <label className="flex items-center pl-3 pr-1 cursor-pointer shrink-0">
          <input
            type="checkbox"
            className="rounded border-[#cbd5e1] text-[#1d4ed8] focus:ring-[#1d4ed8]"
            checked={selected}
            onChange={() => onToggleSelectAssignment?.(conv.assignment_id)}
            aria-label={`Select conversation ${conv.other_participant_name}`}
            onClick={(e) => e.stopPropagation()}
          />
        </label>
      )}
      <button
        type="button"
        onClick={() => onSelect(conv.id)}
        className="flex-1 flex items-start gap-3 px-4 py-3 text-left min-w-0"
        aria-pressed={isActive}
        aria-label={`Conversation with ${conv.other_participant_name}, last message: ${truncate(conv.last_message_preview, 40)}`}
      >
        <div
          className="flex-shrink-0 w-10 h-10 rounded-full bg-[#e2e8f0] flex items-center justify-center text-sm font-semibold text-[#0b2b43]"
          aria-hidden
        >
          {conv.other_participant_avatar || conv.other_participant_name.slice(0, 2).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline justify-between gap-2">
            <span className="font-semibold text-[#1A1A1A] truncate">{conv.other_participant_name}</span>
            <span className="flex-shrink-0 text-[11px] text-[#94a3b8]">
              {formatTime(conv.last_message_at)}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5 mt-0.5">
            {conv.channel === 'supplier' && (
              <span className="text-[10px] font-medium uppercase tracking-wide text-[#0369a1] bg-[#e0f2fe] px-1.5 py-0.5 rounded">
                Provider
              </span>
            )}
            {conv.channel === 'hr' && (
              <span className="text-[10px] font-medium uppercase tracking-wide text-[#64748b] bg-[#f1f5f9] px-1.5 py-0.5 rounded">
                HR
              </span>
            )}
            {conv.list_subtitle && (
              <span className="text-[10px] font-medium text-[#64748b] truncate max-w-[140px]">
                {conv.list_subtitle}
              </span>
            )}
            {conv.case_id && (
              <span className="text-[10px] font-medium uppercase tracking-wide text-[#64748b] bg-[#f1f5f9] px-1.5 py-0.5 rounded">
                Case {truncate(String(conv.case_id), 12)}
              </span>
            )}
            {showArchivedBadge && conv.archived_at && (
              <span className="text-[10px] font-medium text-[#b45309] bg-[#fffbeb] px-1.5 py-0.5 rounded">
                Archived
              </span>
            )}
          </div>
          <div className="flex items-center justify-between gap-2 mt-0.5">
            <span className="text-[13px] text-[#6b7280] truncate">
              {conv.participant_email
                ? truncate(`${conv.participant_email} · ${conv.last_message_preview}`, 56)
                : truncate(conv.last_message_preview, 50)}
            </span>
            {conv.unread_count && conv.unread_count > 0 && (
              <span
                className="flex-shrink-0 min-w-[18px] h-[18px] rounded-full bg-[#1d4ed8] text-white text-[11px] font-medium flex items-center justify-center px-1.5"
                aria-label={`${conv.unread_count} unread`}
              >
                {conv.unread_count > 9 ? '9+' : conv.unread_count}
              </span>
            )}
          </div>
        </div>
      </button>
    </div>
  );
}

export const ConversationList: React.FC<ConversationListProps> = ({
  conversations = [],
  sections,
  activeId,
  onSelect,
  editMode = false,
  selectedAssignmentIds,
  onToggleSelectAssignment,
  showArchivedBadge = false,
}) => {
  const isSectioned = Boolean(sections && sections.length > 0);
  const blocks: ConversationListSection[] =
    sections && sections.length > 0
      ? sections
      : [{ title: '', conversations, emptyHint: undefined }];
  const totalRows = blocks.reduce((n, b) => n + b.conversations.length, 0);

  return (
    <div
      className="h-full flex flex-col bg-white border-r border-[#e2e8f0] overflow-hidden"
      role="list"
      aria-label="Conversations"
    >
      <div className="flex-1 overflow-y-auto">
        {!isSectioned && totalRows === 0 ? (
          <div className="p-6 text-sm text-[#6b7280] text-center">No conversations yet.</div>
        ) : (
          blocks.map((block, bi) => (
            <Fragment key={block.title || `block-${bi}`}>
              {block.title ? (
                <div
                  className="sticky top-0 z-[1] px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-[#64748b] bg-[#f8fafc] border-b border-[#e2e8f0]"
                  role="presentation"
                >
                  {block.title}
                </div>
              ) : null}
              {block.conversations.length === 0 ? (
                <div className="px-4 py-4 text-sm text-[#94a3b8] border-b border-[#e2e8f0]/80">
                  {block.emptyHint ?? 'No threads in this section.'}
                </div>
              ) : (
                block.conversations.map((conv) =>
                  renderConversationRow(
                    conv,
                    activeId === conv.id,
                    onSelect,
                    editMode,
                    selectedAssignmentIds,
                    onToggleSelectAssignment,
                    showArchivedBadge
                  )
                )
              )}
            </Fragment>
          ))
        )}
      </div>
    </div>
  );
};
