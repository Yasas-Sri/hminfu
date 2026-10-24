const fetched = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/London',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
});

export function Footer({ dataAsOf }: { dataAsOf?: string }) {
  return (
    <footer className="pt-8 text-small text-ink-soft">
      Data: Elexon BMRS FUELHH (wind) and WINDFOR, fetched{' '}
      {dataAsOf ? fetched.format(Date.parse(dataAsOf)) : '…'}. Wind as reported by Elexon. The
      January window is our reading of &ldquo;decisions made in January 2026&rdquo;; the default
      09:50 cutoff is N2EX-based. This shows forecast error, not your actual trades. Error =
      forecast &minus; actual.
    </footer>
  );
}
