import { useState, useRef } from 'react';
import { X } from 'lucide-react';
import { useLanguage } from '../LanguageContext';

const overlay = { position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' };

export default function BulkImportModal({ open, listType, onImportText, onImportFile, onClose }) {
  const { t } = useLanguage();
  const [mode, setMode] = useState('text');
  const [text, setText] = useState('');
  const [reason, setReason] = useState('');
  const [file, setFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef(null);

  if (!open) return null;

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setResult(null);
    try {
      if (mode === 'text') {
        const domains = text.split('\n').map(d => d.trim().toLowerCase()).filter(Boolean);
        if (!domains.length) return;
        const res = await onImportText({ domains, reason: reason.trim() });
        setResult(res);
      } else if (file) {
        const res = await onImportFile(file);
        setResult(res);
      }
    } finally {
      setSubmitting(false);
    }
  }

  const modeBtn = (m, labelKey) => (
    <button
      type="button"
      onClick={() => setMode(m)}
      style={{
        background: 'none', border: 'none', cursor: 'pointer', padding: '4px 0',
        fontSize: '13px', color: mode === m ? '#fff' : '#444',
        borderBottom: mode === m ? '1px solid #fff' : '1px solid transparent',
        marginRight: '16px', letterSpacing: '0.04em',
      }}
    >{t(labelKey)}</button>
  );

  return (
    <div style={overlay}>
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '480px', background: '#0c0c0c', border: '1px solid #2a2a2a', padding: '24px' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: '12px', right: '12px', background: 'none', border: 'none', color: '#444', cursor: 'pointer' }}>
          <X size={16} />
        </button>

        <div style={{ fontSize: '11px', color: '#555', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '16px' }}>
          {t('bulk_title', { list: listType })}
        </div>

        <div style={{ marginBottom: '16px' }}>
          {modeBtn('text', 'bulk_paste')}
          {modeBtn('file', 'bulk_upload')}
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {mode === 'text' ? (
            <>
              <textarea
                value={text}
                onChange={e => setText(e.target.value)}
                rows={8}
                placeholder={'example.com\nbadsite.org\nanother.net'}
                style={{ resize: 'vertical' }}
              />
              <input type="text" value={reason} onChange={e => setReason(e.target.value)} placeholder={t('modal_reason_ph')} />
            </>
          ) : (
            <div
              onClick={() => fileRef.current?.click()}
              style={{
                border: '1px dashed #2a2a2a', padding: '32px', textAlign: 'center',
                cursor: 'pointer', color: '#444', fontSize: '13px',
              }}
            >
              {file ? file.name : 'click to select .txt file'}
              <input ref={fileRef} type="file" accept=".txt,.csv" onChange={e => setFile(e.target.files?.[0] || null)} style={{ display: 'none' }} />
            </div>
          )}

          {result && (
            <div style={{ fontSize: '12px', color: '#888', padding: '8px', border: '1px solid #1e1e1e' }}>
              {t('bulk_result', { n: result.added, dupes: result.duplicates > 0 ? t('bulk_skipped', { n: result.duplicates }) : '' })}
            </div>
          )}

          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', paddingTop: '4px' }}>
            <button type="button" onClick={onClose} className="btn-secondary">{t('btn_cancel')}</button>
            <button type="submit" disabled={submitting} className="btn-primary">
              {submitting ? t('btn_importing') : t('btn_import_confirm')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
