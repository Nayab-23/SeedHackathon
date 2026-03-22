import { X } from 'lucide-react';
import { useLanguage } from '../LanguageContext';

const overlay = {
  position: 'fixed', inset: 0, zIndex: 50,
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px',
};

export default function ConfirmDialog({ open, title, message, confirmLabel, onConfirm, onCancel, danger = false }) {
  const { t } = useLanguage();
  if (!open) return null;

  return (
    <div style={overlay}>
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)' }} onClick={onCancel} />
      <div style={{
        position: 'relative', width: '100%', maxWidth: '360px',
        background: '#0c0c0c', border: '1px solid #2a2a2a', padding: '24px',
      }}>
        <button
          onClick={onCancel}
          style={{ position: 'absolute', top: '12px', right: '12px', background: 'none', border: 'none', color: '#444', cursor: 'pointer' }}
        >
          <X size={16} />
        </button>

        <div style={{ fontSize: '12px', color: '#555', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '8px' }}>
          {title}
        </div>
        <p style={{ fontSize: '14px', color: '#888', marginBottom: '24px', lineHeight: 1.5 }}>{message}</p>

        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
          <button onClick={onCancel} className="btn-secondary">{t('cancel_btn')}</button>
          <button onClick={onConfirm} className={danger ? 'btn-danger' : 'btn-primary'}>
            {confirmLabel || t('confirm_btn')}
          </button>
        </div>
      </div>
    </div>
  );
}
