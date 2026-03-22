import { useLanguage } from '../LanguageContext';

const SOFT_RED = '#c07878';

const config = {
  ALLOWED:     { labelKey: 'badge_allowed',     color: '#22c55e', bg: 'rgba(34,197,94,0.08)',   border: 'rgba(34,197,94,0.2)' },
  BLOCKED:     { labelKey: 'badge_blocked',     color: SOFT_RED,  bg: 'rgba(192,120,120,0.08)', border: 'rgba(192,120,120,0.2)' },
  WHITELISTED: { labelKey: 'badge_whitelisted', color: '#6366f1', bg: 'rgba(99,102,241,0.08)',  border: 'rgba(99,102,241,0.2)' },
};

export default function ActionBadge({ action }) {
  const { t } = useLanguage();
  const c = config[action] || config.ALLOWED;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 8px',
      fontSize: '12px', fontWeight: 500, letterSpacing: '0.02em',
      color: c.color,
      background: c.bg,
      border: `1px solid ${c.border}`,
      borderRadius: '4px',
      fontFamily: 'IBM Plex Mono, monospace',
      whiteSpace: 'nowrap',
    }}>
      {t(c.labelKey)}
    </span>
  );
}
