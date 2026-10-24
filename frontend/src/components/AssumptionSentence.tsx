import type { MetaResponse } from '../api/client';
import type { UrlState } from '../hooks/useUrlState';
import { formatDeliveryRange } from '../lib/format';
import { nextDate, ukDate, ukMidnightIso } from '../lib/ukTime';
import { Chip } from './Chip';
import {
  AGG_LABEL,
  AggControl,
  CutoffControl,
  DaysControl,
  LagControl,
  lagLabel,
} from './SentenceControls';

interface Props {
  state: UrlState;
  meta: MetaResponse;
  update: (patch: Partial<UrlState>) => void;
}

/** The assumptions written as a sentence the user can read aloud; each part is a control (DESIGN.md §3.1). */
export function AssumptionSentence({ state, meta, update }: Props) {
  const window_ = meta.default_window;
  const from = state.from ?? window_.from;
  const to = state.to ?? window_.to;
  const cutoff = state.cutoff ?? meta.defaults.cutoff_local;
  const lag = state.lag ?? meta.defaults.publish_lag_minutes;
  const agg = state.agg ?? meta.defaults.aggregation;
  const lastDay = ukDate(new Date(Date.parse(to) - 3600_000).toISOString());
  const [minDay, maxDay] = [
    ukDate(meta.supported_target_range.from),
    ukDate(new Date(Date.parse(meta.supported_target_range.to) - 3600_000).toISOString()),
  ];

  const setDays = (first: string, last: string) => {
    if (!first || !last || first > last) return;
    update({ from: ukMidnightIso(first), to: ukMidnightIso(nextDate(last)) });
  };

  return (
    <div className="max-w-[68ch] text-title text-ink">
      Delivery days{' '}
      <Chip label={formatDeliveryRange(from, to)} title="Delivery days">
        <DaysControl
          first={ukDate(from)}
          last={lastDay}
          min={minDay}
          max={maxDay}
          onChange={setDays}
          onReset={() => update({ from: undefined, to: undefined })}
        />
      </Chip>
      , auction closing at{' '}
      <Chip label={cutoff} title="Auction closes">
        <CutoffControl value={cutoff} fallback={meta.defaults.cutoff_local} update={update} />
      </Chip>{' '}
      the day before, forecasts usable{' '}
      <Chip label={lagLabel(lag)} title="Forecasts usable">
        <LagControl value={lag} update={update} />
      </Chip>
      , comparing forecasts with{' '}
      <Chip label={AGG_LABEL[agg]} title="Compare forecasts with">
        <AggControl value={agg} update={update} />
      </Chip>
      .
    </div>
  );
}
