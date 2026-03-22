import { useState } from 'react';
import { X } from 'lucide-react';
import { useLanguage } from '../LanguageContext';

const overlay = {
  position: 'fixed', inset: 0, zIndex: 50,
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px',
};

export default function AddDomainModal({ open, listType, onAdd, onClose }) {
  const { t } = useLanguage();
  const [domain, setDomain] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!domain.trim()) return;
    setSubmitting(true);
    try {
      await onAdd({ domain: domain.trim().toLowerCase(), reason: reason.trim() });
      setDomain(''); setReason(''); onClose();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={overlay}>
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '400px', background: '#0c0c0c', border: '1px solid #2a2a2a', padding: '24px' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: '12px', right: '12px', background: 'none', border: 'none', color: '#444', cursor: 'pointer' }}>
          <X size={16} />
        </button>

        <div style={{ fontSize: '11px', color: '#555', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '20px' }}>
          {t('modal_add_title', { list: listType })}
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '6px', letterSpacing: '0.06em' }}>{t('modal_domain_label')}</div>
            <input type="text" value={domain} onChange={e => setDomain(e.target.value)} placeholder="example.com" autoFocus />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '6px', letterSpacing: '0.06em' }}>{t('modal_reason_label')}</div>
            <input type="text" value={reason} onChange={e => setReason(e.target.value)} placeholder={t('modal_reason_ph')} />
          </div>
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', paddingTop: '8px' }}>
            <button type="button" onClick={onClose} className="btn-secondary">{t('btn_cancel')}</button>
            <button type="submit" disabled={!domain.trim() || submitting} className="btn-primary">
              {submitting ? t('btn_adding') : t('btn_add_confirm')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
