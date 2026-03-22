import { useState } from 'react';
import { X } from 'lucide-react';
import { useLanguage } from '../LanguageContext';

const overlay = { position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' };

const DURATIONS = [
  { label: '30m', value: 30 },
  { label: '1h', value: 60 },
  { label: '1.5h', value: 90 },
  { label: '2h', value: 120 },
  { label: '3h', value: 180 },
];

export default function SetFocusModal({ open, profileName, onClose, onSet }) {
  const { t } = useLanguage();
  const [note, setNote] = useState('');
  const [duration, setDuration] = useState(60);
  const [customDuration, setCustomDuration] = useState('');
  const [strictness, setStrictness] = useState('moderate');
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const STRICTNESS = [
    { value: 'relaxed',  labelKey: 'strict_relaxed',  descKey: 'strict_relaxed_desc' },
    { value: 'moderate', labelKey: 'strict_moderate', descKey: 'strict_moderate_desc' },
    { value: 'strict',   labelKey: 'strict_strict',   descKey: 'strict_strict_desc' },
  ];

  const effectiveDuration = customDuration ? parseInt(customDuration, 10) : duration;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!note.trim() || !effectiveDuration) return;
    setSubmitting(true);
    try {
      await onSet({ note: note.trim(), duration_minutes: effectiveDuration, strictness });
      setNote(''); setDuration(60); setCustomDuration(''); setStrictness('moderate'); onClose();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={overlay}>
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '420px', background: '#0c0c0c', border: '1px solid #2a2a2a', padding: '24px', maxHeight: '90vh', overflowY: 'auto' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: '12px', right: '12px', background: 'none', border: 'none', color: '#444', cursor: 'pointer' }}>
          <X size={16} />
        </button>

        <div style={{ fontSize: '11px', color: '#555', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '4px' }}>
          {t('focus_modal_title')}
        </div>
        <div style={{ fontSize: '13px', color: '#444', marginBottom: '20px' }}>{t('focus_modal_for', { name: profileName })}</div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '6px' }}>{t('focus_what')}</div>
            <input type="text" value={note} onChange={e => setNote(e.target.value)} placeholder={t('focus_what_ph')} autoFocus />
          </div>

          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '8px' }}>{t('focus_duration')}</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
              {DURATIONS.map(p => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => { setDuration(p.value); setCustomDuration(''); }}
                  style={{
                    background: 'none', cursor: 'pointer', padding: '4px 10px',
                    fontSize: '13px', border: '1px solid',
                    borderColor: duration === p.value && !customDuration ? '#888' : '#1e1e1e',
                    color: duration === p.value && !customDuration ? '#fff' : '#555',
                    transition: 'all 0.1s',
                  }}
                >
                  {p.label}
                </button>
              ))}
              <input
                type="number"
                value={customDuration}
                onChange={e => setCustomDuration(e.target.value)}
                placeholder={t('focus_custom_ph')}
                min={1}
                style={{ width: '110px' }}
              />
            </div>
          </div>

          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '8px' }}>{t('focus_strictness')}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {STRICTNESS.map(opt => (
                <label
                  key={opt.value}
                  style={{
                    display: 'flex', gap: '10px', alignItems: 'flex-start',
                    padding: '10px 12px', border: '1px solid',
                    borderColor: strictness === opt.value ? '#333' : '#111',
                    cursor: 'pointer', transition: 'border-color 0.1s',
                  }}
                >
                  <input
                    type="radio"
                    name="strictness"
                    value={opt.value}
                    checked={strictness === opt.value}
                    onChange={() => setStrictness(opt.value)}
                    style={{ width: 'auto', marginTop: '2px', accentColor: '#fff' }}
                  />
                  <div>
                    <div style={{ fontSize: '13px', color: strictness === opt.value ? '#ccc' : '#555' }}>{t(opt.labelKey)}</div>
                    <div style={{ fontSize: '11px', color: '#333', marginTop: '2px' }}>{t(opt.descKey)}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', paddingTop: '4px' }}>
            <button type="button" onClick={onClose} className="btn-secondary">{t('btn_cancel')}</button>
            <button type="submit" disabled={!note.trim() || !effectiveDuration || submitting} className="btn-primary">
              {submitting ? t('btn_starting') : t('btn_start')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
