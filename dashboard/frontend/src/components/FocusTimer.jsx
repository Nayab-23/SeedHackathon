import { useState, useEffect } from 'react';
import { Clock, AlertTriangle } from 'lucide-react';
import { useLanguage } from '../LanguageContext';

export default function FocusTimer({ expiresAt, note, strictness }) {
  const { t } = useLanguage();
  const [remaining, setRemaining] = useState('');
  const [urgent, setUrgent] = useState(false);

  useEffect(() => {
    function update() {
      const diff = new Date(expiresAt).getTime() - Date.now();
      if (diff <= 0) { setRemaining(t('focus_expired')); setUrgent(false); return; }
      setUrgent(diff < 5 * 60 * 1000);
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setRemaining(h > 0 ? `${h}h ${m}m ${s}s` : `${m}m ${s}s`);
    }
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [expiresAt, t]);

  const color = urgent ? '#f59e0b' : '#6366f1';
  const bg = urgent ? 'rgba(245,158,11,0.06)' : 'rgba(99,102,241,0.06)';
  const border = urgent ? 'rgba(245,158,11,0.25)' : 'rgba(99,102,241,0.25)';

  const strictnessColor = { relaxed: '#22c55e', moderate: '#6366f1', strict: '#c07878' };
  const strictnessLabel = {
    relaxed: t('strict_relaxed'),
    moderate: t('strict_moderate'),
    strict: t('strict_strict'),
  };

  return (
    <div style={{ border: `1px solid ${border}`, padding: '12px 14px', background: bg, borderRadius: '6px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
        {urgent
          ? <AlertTriangle size={14} style={{ color: '#f59e0b' }} />
          : <Clock size={14} style={{ color: '#6366f1' }} />
        }
        <span style={{
          fontFamily: 'IBM Plex Mono, monospace', fontSize: '20px', fontWeight: 700,
          color, letterSpacing: '-0.01em', fontVariantNumeric: 'tabular-nums',
        }}>
          {remaining}
        </span>
        <span style={{
          fontSize: '11px', color: strictnessColor[strictness] || '#6366f1',
          textTransform: 'uppercase', letterSpacing: '0.08em',
          background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '3px',
        }}>
          {strictnessLabel[strictness] || strictness}
        </span>
      </div>
      <div style={{ fontSize: '13px', color: '#8888aa', fontStyle: 'italic' }}>{note}</div>
    </div>
  );
}
