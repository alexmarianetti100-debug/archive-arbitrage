import { useState, useEffect, useRef } from 'react';
import { Check, X, ExternalLink, AlertTriangle } from 'lucide-react';
import { useItemComps, useCompFeedback } from '../hooks/useApi';
import type { RejectionReason } from '../types';

const REJECTION_REASONS: { value: RejectionReason; label: string }[] = [
  { value: 'wrong_model', label: 'Wrong model' },
  { value: 'wrong_condition', label: 'Wrong condition' },
  { value: 'wrong_brand', label: 'Wrong brand' },
  { value: 'outlier', label: 'Outlier price' },
  { value: 'other', label: 'Other' },
];

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return '—';
  }
}

function formatPrice(price: number | null | undefined): string {
  if (price == null) return '—';
  return `$${Math.round(price)}`;
}

interface CompTableProps {
  itemId: number;
}

export function CompTable({ itemId }: CompTableProps) {
  const { data, isLoading } = useItemComps(itemId);
  const feedback = useCompFeedback(itemId);

  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Auto-clear toast after 5s
  useEffect(() => {
    if (toast) {
      if (toastTimer.current) clearTimeout(toastTimer.current);
      toastTimer.current = setTimeout(() => setToast(null), 5000);
    }
    return () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, [toast]);

  // Close dropdown on outside click
  useEffect(() => {
    if (rejectingId === null) return;
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setRejectingId(null);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [rejectingId]);

  function handleAccept(itemCompId: number) {
    feedback.mutate({ itemCompId, status: 'accepted' });
  }

  function handleReject(itemCompId: number, reason: RejectionReason) {
    feedback.mutate(
      { itemCompId, status: 'rejected', reason },
      {
        onSuccess: (result) => {
          setRejectingId(null);
          if (result.regrade.triggered) {
            const gb = result.regrade.grade_before ?? '?';
            const ga = result.regrade.grade_after ?? '?';
            const pb = result.regrade.price_before != null ? formatPrice(result.regrade.price_before) : '?';
            const pa = result.regrade.price_after != null ? formatPrice(result.regrade.price_after) : '?';
            setToast(`Re-graded: ${gb} → ${ga} · ${pb} → ${pa}`);
          } else if (result.regrade.flagged_for_review) {
            setToast('Flagged for review — too few comps remaining');
          }
        },
      },
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(3)].map((_, i) => (
          <div
            key={i}
            className="h-12 bg-surface rounded border border-border animate-skeleton"
          />
        ))}
      </div>
    );
  }

  // Empty state
  if (!data || data.comps.length === 0) {
    return (
      <p className="font-mono text-[11px] text-text-muted py-4 text-center">
        No comps assigned to this item
      </p>
    );
  }

  const { comps, total, accepted, rejected, pending } = data;
  const remaining = total - rejected;
  const showWarning = remaining < 3;

  return (
    <div className="space-y-3">
      {/* Warning banner */}
      {showWarning && (
        <div className="flex items-center gap-2 px-3 py-2 rounded bg-signal-amber/10 border border-signal-amber/20">
          <AlertTriangle className="w-3.5 h-3.5 text-signal-amber flex-shrink-0" />
          <span className="font-mono text-[11px] text-signal-amber">
            Only {remaining} comp{remaining !== 1 ? 's' : ''} remaining — results may be unreliable
          </span>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="px-3 py-2 rounded bg-accent/10 border border-accent/20 font-mono text-[11px] text-accent transition-opacity duration-300">
          {toast}
        </div>
      )}

      {/* Summary line */}
      <div className="font-mono text-[10px] text-text-muted flex items-center gap-2">
        <span>{total} comps</span>
        <span className="text-text-muted">·</span>
        {accepted > 0 && <span className="text-signal-green">{accepted} accepted</span>}
        {rejected > 0 && <span className="text-signal-red">{rejected} rejected</span>}
        {pending > 0 && <span className="text-text-secondary">{pending} pending</span>}
      </div>

      {/* Comp rows */}
      <div className="space-y-1.5">
        {comps.map((comp) => {
          const isRejected = comp.feedback_status === 'rejected';
          const isAccepted = comp.feedback_status === 'accepted';
          const isPending = comp.feedback_status === 'pending';

          const rowBorder = isRejected
            ? 'border-signal-red/10 bg-signal-red/5 opacity-50'
            : isAccepted
            ? 'border-signal-green/10 bg-signal-green/5'
            : 'border-border bg-surface';

          return (
            <div
              key={comp.item_comp_id}
              className={`flex items-center gap-2 px-2.5 py-2 rounded border ${rowBorder} transition-colors`}
            >
              {/* Rank */}
              <span className="font-mono text-[10px] text-text-muted text-center w-4 flex-shrink-0">
                {comp.rank}
              </span>

              {/* Title + metadata */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`font-sans text-xs truncate ${
                      isRejected ? 'line-through text-text-muted' : 'text-text-primary'
                    }`}
                  >
                    {comp.title}
                  </span>
                  {comp.sold_url && (
                    <a
                      href={comp.sold_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-shrink-0 text-text-muted hover:text-accent transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-0.5 font-mono text-[10px] text-text-muted">
                  {comp.source && (
                    <span className="uppercase">{comp.source}</span>
                  )}
                  {comp.condition && <span>{comp.condition}</span>}
                  {isRejected && comp.rejection_reason && (
                    <span className="text-signal-red">{comp.rejection_reason.replace(/_/g, ' ')}</span>
                  )}
                </div>
              </div>

              {/* Price */}
              <span
                className={`font-mono text-xs flex-shrink-0 ${
                  isRejected ? 'line-through text-text-muted' : 'text-text-primary'
                }`}
              >
                {formatPrice(comp.sold_price)}
              </span>

              {/* Date */}
              <span
                className={`font-mono text-[10px] w-14 text-right flex-shrink-0 ${
                  isRejected ? 'line-through text-text-muted' : 'text-text-muted'
                }`}
              >
                {formatDate(comp.sold_date)}
              </span>

              {/* Score */}
              <span
                className={`font-mono text-[10px] w-8 text-right flex-shrink-0 ${
                  isRejected ? 'line-through text-text-muted' : 'text-text-secondary'
                }`}
              >
                {Math.round(comp.similarity_score * 100)}%
              </span>

              {/* Action buttons */}
              <div className="flex items-center gap-1 flex-shrink-0 relative">
                {isPending && (
                  <>
                    <button
                      onClick={() => handleAccept(comp.item_comp_id)}
                      className="p-1 rounded hover:bg-signal-green/10 text-text-muted hover:text-signal-green transition-colors"
                      title="Accept comp"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                    <div className="relative" ref={rejectingId === comp.item_comp_id ? dropdownRef : undefined}>
                      <button
                        onClick={() =>
                          setRejectingId(
                            rejectingId === comp.item_comp_id ? null : comp.item_comp_id,
                          )
                        }
                        className="p-1 rounded hover:bg-signal-red/10 text-text-muted hover:text-signal-red transition-colors"
                        title="Reject comp"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                      {rejectingId === comp.item_comp_id && (
                        <div className="absolute right-0 top-full mt-1 z-20 bg-surface border border-border rounded shadow-lg py-1 min-w-[140px]">
                          {REJECTION_REASONS.map((r) => (
                            <button
                              key={r.value}
                              onClick={() => handleReject(comp.item_comp_id, r.value)}
                              className="w-full text-left px-3 py-1.5 font-mono text-[11px] text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors"
                            >
                              {r.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </>
                )}
                {isAccepted && (
                  <span className="p-1 text-signal-green">
                    <Check className="w-3.5 h-3.5" />
                  </span>
                )}
                {isRejected && (
                  <span className="p-1 text-signal-red">
                    <X className="w-3.5 h-3.5" />
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
