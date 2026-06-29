'use client';

import { PRICING_BREAKDOWN_ROWS, estimateCount } from '@/lib/pricing';

interface CreditBreakdownPanelProps {
  title: string;
  colVideoType: string;
  colDuration: string;
  colCredits: string;
  colPlanGets: string;
  referenceCredits: number;
  rows?: typeof PRICING_BREAKDOWN_ROWS;
  t: (key: string) => string;
}

function formatDuration(duration: string, t: (key: string) => string): string {
  if (duration === 'full') return t('upgrade.breakdown.duration.full');
  if (duration === 'sheet') return t('upgrade.breakdown.duration.sheet');
  return duration;
}

export default function CreditBreakdownPanel({
  title,
  colVideoType,
  colDuration,
  colCredits,
  colPlanGets,
  referenceCredits,
  rows = PRICING_BREAKDOWN_ROWS,
  t,
}: CreditBreakdownPanelProps) {
  return (
    <details className="upgrade-breakdown">
      <summary className="upgrade-breakdown-summary">
        <span className="upgrade-breakdown-summary-text">{title}</span>
        <svg className="upgrade-breakdown-chevron" viewBox="0 0 24 24" aria-hidden="true">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </summary>
      <div className="upgrade-breakdown-table-wrap">
        <table className="upgrade-breakdown-table">
          <thead>
            <tr>
              <th>{colVideoType}</th>
              <th>{colDuration}</th>
              <th>{colCredits}</th>
              <th>{colPlanGets}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td>{t(`upgrade.breakdown.row.${row.key}`)}</td>
                <td>{formatDuration(row.duration, t)}</td>
                <td>{row.credits}</td>
                <td>~{estimateCount(referenceCredits, row.credits)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
