import { Footer } from './components/Footer';
import { Header } from './components/Header';
import { ErrorNotice } from './components/States';
import { Accuracy } from './features/accuracy/Accuracy';
import { Explorer } from './features/explorer/Explorer';
import { useMeta } from './hooks/queries';
import { useUrlState } from './hooks/useUrlState';

export function App() {
  const [state, update] = useUrlState();
  const meta = useMeta();
  const resetWindow = () => update({ from: undefined, to: undefined });

  return (
    <div className="mx-auto max-w-[1240px] px-8 py-8 max-sm:px-4">
      {meta.isError && (
        <ErrorNotice message={meta.error.message} onRetry={() => void meta.refetch()} />
      )}
      {meta.data ? (
        <>
          <Header state={state} meta={meta.data} update={update} />
          <main
            id="view"
            role="tabpanel"
            className="relative rounded-sheet border border-rule bg-sheet p-6 max-sm:p-4"
          >
            {state.tab === 'accuracy' ? (
              <Accuracy state={state} onReset={resetWindow} />
            ) : (
              <Explorer state={state} onReset={resetWindow} />
            )}
          </main>
        </>
      ) : (
        !meta.isError && <p className="text-ui text-ink-soft">Loading January data</p>
      )}
      <Footer dataAsOf={meta.data?.data_as_of} />
    </div>
  );
}
