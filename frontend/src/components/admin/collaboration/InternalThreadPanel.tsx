import React, { useCallback, useEffect, useState } from 'react';
import { adminCollaborationAPI } from '../../../api/client';
import { MentionAutocomplete } from './MentionAutocomplete';

type Thread = {
  id: string;
  status: string;
  comment_count: number;
  last_comment_at?: string;
  is_unread?: boolean;
};

type Comment = {
  id: string;
  author_user_id: string;
  author_display_name?: string;
  body: string;
  created_at: string;
  edited_at?: string;
  is_edited?: boolean;
  parent_comment_id?: string;
  can_edit?: boolean;
  can_delete?: boolean;
};

interface Props {
  targetType: 'review_queue_item' | 'ops_notification' | 'staged_resource_candidate' | 'staged_event_candidate' | 'live_resource' | 'live_event';
  targetId: string;
  title?: string;
  onSummaryChange?: (summary: { comment_count: number; last_comment_at?: string; is_unread?: boolean } | null) => void;
}

export const InternalThreadPanel: React.FC<Props> = ({
  targetType,
  targetId,
  title = 'Internal discussion',
  onSummaryChange,
}) => {
  const [thread, setThread] = useState<Thread | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newBody, setNewBody] = useState('');
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState('');
  const [editId, setEditId] = useState<string | null>(null);
  const [editBody, setEditBody] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!targetId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await adminCollaborationAPI.getThread(targetType, targetId);
      const t = res.thread;
      setThread(t || null);
      if (t?.id) {
        const comRes = await adminCollaborationAPI.getComments(t.id);
        setComments(comRes.comments || []);
        await adminCollaborationAPI.markRead(t.id);
        onSummaryChange?.({
          comment_count: t.comment_count,
          last_comment_at: t.last_comment_at,
          is_unread: false,
        });
      } else {
        setComments([]);
        onSummaryChange?.(null);
      }
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [targetType, targetId, onSummaryChange]);

  useEffect(() => {
    load();
  }, [load]);

  const handleStartDiscussion = async () => {
    if (!newBody.trim() || submitting) return;
    setSubmitting(true);
    try {
      const res = await adminCollaborationAPI.getOrCreateThread(targetType, targetId, title);
      const t = res.thread;
      if (t?.id) {
        await adminCollaborationAPI.createComment(t.id, newBody.trim());
        setNewBody('');
        await load();
      }
    } catch (e) {
      setError((e as Error)?.message || 'Failed to post');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddComment = async () => {
    const body = replyTo ? replyBody : newBody;
    if (!body.trim() || !thread?.id || submitting) return;
    setSubmitting(true);
    try {
      await adminCollaborationAPI.createComment(thread.id, body.trim(), replyTo || undefined);
      setNewBody('');
      setReplyBody('');
      setReplyTo(null);
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Failed to post');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = async () => {
    if (!editId || !editBody.trim() || submitting) return;
    setSubmitting(true);
    try {
      await adminCollaborationAPI.editComment(editId, editBody.trim());
      setEditId(null);
      setEditBody('');
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Failed to edit');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (commentId: string) => {
    if (!confirm('Delete this comment?')) return;
    setSubmitting(true);
    try {
      await adminCollaborationAPI.deleteComment(commentId);
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Failed to delete');
    } finally {
      setSubmitting(false);
    }
  };

  const handleResolve = async () => {
    if (!thread?.id || submitting) return;
    setSubmitting(true);
    try {
      await adminCollaborationAPI.resolveThread(thread.id);
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReopen = async () => {
    if (!thread?.id || submitting) return;
    setSubmitting(true);
    try {
      await adminCollaborationAPI.reopenThread(thread.id);
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (!targetId) return null;

  const rootComments = comments.filter((c) => !c.parent_comment_id);
  const replyMap = comments.reduce<Record<string, Comment[]>>((acc, c) => {
    if (c.parent_comment_id) {
      (acc[c.parent_comment_id] = acc[c.parent_comment_id] || []).push(c);
    }
    return acc;
  }, {});

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
        {title}
        {thread && (
          <span
            className={`rounded px-2 py-0.5 text-xs ${
              thread.status === 'open'
                ? 'bg-green-100 text-green-800'
                : thread.status === 'resolved'
                ? 'bg-slate-100 text-slate-600'
                : 'bg-slate-200 text-slate-600'
            }`}
          >
            {thread.status}
          </span>
        )}
        {thread && thread.comment_count > 0 && (
          <span className="text-xs text-slate-500">({thread.comment_count} comments)</span>
        )}
      </h3>

      {error && <div className="mb-3 rounded bg-red-50 p-2 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="py-4 text-center text-sm text-slate-500">Loading...</div>
      ) : !thread ? (
        <div className="space-y-3">
          <p className="text-sm text-slate-600">No discussion yet. Start an internal discussion for this item.</p>
          <MentionAutocomplete
            value={newBody}
            onChange={setNewBody}
            placeholder="Add a comment... Type @ to mention someone."
            rows={3}
          />
          <button
            type="button"
            onClick={handleStartDiscussion}
            disabled={!newBody.trim() || submitting}
            className="rounded bg-[#0b2b43] px-3 py-1 text-sm text-white hover:bg-[#0d3552] disabled:opacity-50"
          >
            Start discussion
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="max-h-64 space-y-3 overflow-y-auto">
            {rootComments.length === 0 ? (
              <p className="text-sm text-slate-500">No comments yet.</p>
            ) : (
              rootComments.map((c) => (
                <div key={c.id} className="rounded bg-slate-50 p-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1 text-xs text-slate-500">
                        <span className="font-medium">{c.author_display_name ?? c.author_user_id?.slice(0, 8) + '…'}</span>
                        <span>{new Date(c.created_at).toLocaleString()}</span>
                        {c.is_edited && <span>(edited)</span>}
                      </div>
                      {editId === c.id ? (
                        <div className="mt-1">
                          <textarea
                            className="w-full rounded border border-slate-300 p-1 text-sm"
                            rows={2}
                            value={editBody}
                            onChange={(e) => setEditBody(e.target.value)}
                          />
                          <div className="mt-1 flex gap-1">
                            <button
                              type="button"
                              onClick={handleEdit}
                              disabled={submitting}
                              className="rounded bg-slate-200 px-2 py-0.5 text-xs"
                            >
                              Save
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditId(null)}
                              className="rounded bg-slate-100 px-2 py-0.5 text-xs"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="mt-0.5 whitespace-pre-wrap break-words text-sm">{c.body}</p>
                      )}
                    </div>
                    {editId !== c.id && c.can_edit && (
                      <div className="flex shrink-0 gap-1">
                        <button
                          type="button"
                          onClick={() => {
                            setEditId(c.id);
                            setEditBody(c.body);
                          }}
                          className="text-xs text-slate-500 hover:text-slate-700"
                        >
                          Edit
                        </button>
                        {c.can_delete && (
                          <button
                            type="button"
                            onClick={() => handleDelete(c.id)}
                            className="text-xs text-red-500 hover:text-red-700"
                          >
                            Delete
                          </button>
                        )}
                        {thread.status === 'open' && (
                          <button
                            type="button"
                            onClick={() => setReplyTo(c.id)}
                            className="text-xs text-slate-500 hover:text-slate-700"
                          >
                            Reply
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                  {(replyMap[c.id] || []).map((r) => (
                    <div key={r.id} className="ml-4 mt-2 border-l-2 border-slate-200 pl-2">
                      <div className="flex items-center gap-1 text-xs text-slate-500">
                        <span>{r.author_display_name ?? r.author_user_id?.slice(0, 8) + '…'}</span>
                        <span>{new Date(r.created_at).toLocaleString()}</span>
                      </div>
                      <p className="whitespace-pre-wrap break-words text-sm">{r.body}</p>
                    </div>
                  ))}
                  {replyTo === c.id && (
                    <div className="ml-4 mt-2">
                      <textarea
                        className="w-full rounded border border-slate-300 p-1 text-sm"
                        rows={2}
                        placeholder="Reply..."
                        value={replyBody}
                        onChange={(e) => setReplyBody(e.target.value)}
                      />
                      <div className="mt-1 flex gap-1">
                        <button
                          type="button"
                          onClick={handleAddComment}
                          disabled={!replyBody.trim() || submitting}
                          className="rounded bg-slate-200 px-2 py-0.5 text-xs"
                        >
                          Post reply
                        </button>
                        <button
                          type="button"
                          onClick={() => setReplyTo(null)}
                          className="rounded bg-slate-100 px-2 py-0.5 text-xs"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {thread.status === 'closed' && (
            <p className="text-sm text-slate-500">Thread closed — reopen to add comments.</p>
          )}
          {thread.status === 'open' && !replyTo && (
            <div className="space-y-2">
              <MentionAutocomplete
                value={newBody}
                onChange={setNewBody}
                placeholder="Add a comment... Type @ to mention someone."
                rows={2}
              />
              <button
                type="button"
                onClick={handleAddComment}
                disabled={!newBody.trim() || submitting}
                className="rounded bg-[#0b2b43] px-3 py-1 text-sm text-white hover:bg-[#0d3552] disabled:opacity-50"
              >
                Add comment
              </button>
            </div>
          )}

          <div className="flex gap-2 pt-2 border-t border-slate-200">
            {thread.status === 'open' && (
              <button
                type="button"
                onClick={handleResolve}
                disabled={submitting}
                className="rounded bg-green-100 px-2 py-1 text-xs text-green-800 hover:bg-green-200"
              >
                Resolve discussion
              </button>
            )}
            {(thread.status === 'resolved' || thread.status === 'closed') && (
              <button
                type="button"
                onClick={handleReopen}
                disabled={submitting}
                className="rounded bg-blue-100 px-2 py-1 text-xs text-blue-800 hover:bg-blue-200"
              >
                Reopen discussion
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
