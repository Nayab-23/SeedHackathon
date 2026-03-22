import { useState } from 'react';
import { X } from 'lucide-react';
import { useLanguage } from '../LanguageContext';

const overlay = { position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' };

export default function CreateProfileModal({ open, onClose, onCreate }) {
  const { t } = useLanguage();
  const [name, setName] = useState('');
  const [ip, setIp] = useState('');
  const [label, setLabel] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      await onCreate({ name: name.trim(), device: ip.trim() ? { ip: ip.trim(), label: label.trim() } : null });
      setName(''); setIp(''); setLabel(''); onClose();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={overlay}>
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '380px', background: '#0c0c0c', border: '1px solid #2a2a2a', padding: '24px' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: '12px', right: '12px', background: 'none', border: 'none', color: '#444', cursor: 'pointer' }}>
          <X size={16} />
        </button>

        <div style={{ fontSize: '11px', color: '#555', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '20px' }}>
          {t('create_profile_title')}
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '6px' }}>{t('name_label')}</div>
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder={t('name_placeholder')} autoFocus />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '6px' }}>{t('ip_label')}</div>
            <input type="text" value={ip} onChange={e => setIp(e.target.value)} placeholder="100.100.14.23" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '6px' }}>{t('device_label')}</div>
            <input type="text" value={label} onChange={e => setLabel(e.target.value)} placeholder={t('label_placeholder')} />
          </div>
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', paddingTop: '8px' }}>
            <button type="button" onClick={onClose} className="btn-secondary">{t('btn_cancel')}</button>
            <button type="submit" disabled={!name.trim() || submitting} className="btn-primary">
              {submitting ? t('btn_creating') : t('btn_create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
