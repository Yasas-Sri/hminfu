import { EmptyRange, ErrorNotice, ProgressBar } from '../../components/States';
import { toParams, useMetrics } from '../../hooks/queries';
import type { UrlState } from '../../hooks/useUrlState';
import { Breakdowns } from './Breakdowns';
import { HowCalculated } from './HowCalculated';
import { Ledger } from './Ledger';
import { biasNote, summarySentence } from './summary';

export function Accuracy({ state, onReset }: { state: UrlState; onReset: () => void }) {
  const q = useMetrics(toParams(state));
  if (q.isError) return <ErrorNotice message={q.error.message} onRetry={() => void q.refetch()} />;
  if (!q.data) return <p className="text-ui text-ink-soft">Loading January data</p>;
  const m = q.data;
  const sentence = summarySentence(m);
  const note = biasNote(m);

  return (
    <div className="flex flex-col gap-8">
      <ProgressBar active={q.isFetching} />
      {m.n === 0 ? (
        <EmptyRange onReset={onReset} />
      ) : (
        <div className={`flex flex-col gap-6 ${q.isPlaceholderData ? 'opacity-60' : ''}`}>
          <p className="m-0 max-w-[68ch] text-body">
            {sentence} {note}
          </p>
          <Ledger metrics={m} />
          <HowCalculated />
        </div>
      )}
      <div className="border-t border-rule pt-8">
        <Breakdowns state={state} />
      </div>
    </div>
  );
}
