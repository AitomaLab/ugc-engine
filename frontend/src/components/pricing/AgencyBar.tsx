'use client';

interface AgencyBarProps {
  title: string;
  subtitle: string;
  cta: string;
  onContact: () => void;
}

export default function AgencyBar({ title, subtitle, cta, onContact }: AgencyBarProps) {
  return (
    <div className="upgrade-agency-bar">
      <div>
        <p className="upgrade-agency-title">{title}</p>
        <p className="upgrade-agency-subtitle">{subtitle}</p>
      </div>
      <button type="button" className="upgrade-btn upgrade-btn-primary upgrade-agency-cta" onClick={onContact}>
        {cta}
      </button>
    </div>
  );
}
