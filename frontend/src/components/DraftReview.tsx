"use client";

import { useState } from "react";

export interface Draft {
  id: string;
  task_id: string;
  task_type:
    | "email_reply"
    | "slack_message"
    | "doc_update"
    | "meeting_reschedule"
    | "linkedin_post"
    | "cancel_appointment";
  subject?: string;
  recipient?: string;
  channel?: string;
  body: string;
  cost_fet: number;
  timestamp: string;
}

const TYPE_LABELS: Record<Draft["task_type"], { label: string; icon: string }> = {
  email_reply: { label: "Email Draft", icon: "📧" },
  slack_message: { label: "Slack Message", icon: "💬" },
  doc_update: { label: "Doc Update", icon: "📝" },
  meeting_reschedule: { label: "Meeting Reschedule", icon: "📅" },
  linkedin_post: { label: "LinkedIn Post", icon: "💼" },
  cancel_appointment: { label: "Cancellation", icon: "🚫" },
};

interface DraftReviewProps {
  draft: Draft;
  onApprove: (draftId: string) => void;
  onEdit: (draftId: string, editedBody: string) => void;
  onReject: (draftId: string) => void;
}

export default function DraftReview({
  draft,
  onApprove,
  onEdit,
  onReject,
}: DraftReviewProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedBody, setEditedBody] = useState(draft.body);
  const typeInfo = TYPE_LABELS[draft.task_type];

  const handleSaveEdit = () => {
    onEdit(draft.id, editedBody);
    setIsEditing(false);
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span>{typeInfo.icon}</span>
          <span className="text-xs font-medium text-cyan-400">
            {typeInfo.label}
          </span>
          <span className="text-[10px] text-zinc-600">
            via GhostWorker
          </span>
        </div>
        <span className="text-[10px] text-zinc-600 tabular-nums">
          {draft.cost_fet} FET
        </span>
      </div>

      {/* Meta */}
      <div className="border-b border-zinc-800/50 px-4 py-2 space-y-1">
        {draft.recipient && (
          <div className="flex gap-2 text-xs">
            <span className="text-zinc-600 w-8">To:</span>
            <span className="text-zinc-300">{draft.recipient}</span>
          </div>
        )}
        {draft.channel && (
          <div className="flex gap-2 text-xs">
            <span className="text-zinc-600 w-8">Ch:</span>
            <span className="text-zinc-300">#{draft.channel}</span>
          </div>
        )}
        {draft.subject && (
          <div className="flex gap-2 text-xs">
            <span className="text-zinc-600 w-8">Re:</span>
            <span className="text-zinc-300">{draft.subject}</span>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="px-4 py-3">
        {isEditing ? (
          <textarea
            value={editedBody}
            onChange={(e) => setEditedBody(e.target.value)}
            rows={5}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 focus:border-zinc-600 focus:outline-none resize-none"
            autoFocus
          />
        ) : (
          <p className="text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">
            {draft.body}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2 border-t border-zinc-800 px-4 py-3">
        {isEditing ? (
          <>
            <button
              onClick={() => {
                setIsEditing(false);
                setEditedBody(draft.body);
              }}
              className="flex-1 rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 hover:bg-zinc-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveEdit}
              className="flex-1 rounded-lg bg-cyan-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-cyan-500 transition-colors"
            >
              Save & Send
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => onReject(draft.id)}
              className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-500 hover:text-red-400 hover:border-red-500/30 transition-colors"
            >
              Reject
            </button>
            <button
              onClick={() => setIsEditing(true)}
              className="flex-1 rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 transition-colors"
            >
              Edit
            </button>
            <button
              onClick={() => onApprove(draft.id)}
              className="flex-1 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-500 transition-colors"
            >
              {draft.task_type === "email_reply" ? "Approve & Open Gmail" : "Approve & Send"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
