import type { MetaResponse } from '../api/client';
import type { Tab, UrlState } from '../hooks/useUrlState';
import { AssumptionSentence } from './AssumptionSentence';

const TABS: { id: Tab; label: string }[] = [
  { id: 'explorer', label: 'Forecast vs actual' },
  { id: 'accuracy', label: 'Accuracy' },
];

export function Header(props: {
  state: UrlState;
  meta: MetaResponse;
  update: (p: Partial<UrlState>) => void;
}) {
  const { state, update } = props;
  return (
    <header className="flex flex-col gap-4 pb-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="m-0 text-section text-ink-soft">Wind forecast at the day-ahead cutoff</h1>
        <div role="tablist" aria-label="View" className="flex rounded-input border border-rule">
          {TABS.map((t) => {
            const selected = state.tab === t.id;
            return (
              <button
                key={t.id}
                role="tab"
                type="button"
                aria-selected={selected}
                aria-controls="view"
                onClick={() => update({ tab: t.id })}
                className={`border-b-2 px-3 py-1 text-ui ${selected ? 'border-forecast bg-sheet font-medium text-forecast' : 'border-transparent text-ink-soft'}`}
              >
                {t.label}
              </button>
            );
          })}
        </div>
      </div>
      <AssumptionSentence {...props} />
    </header>
  );
}
