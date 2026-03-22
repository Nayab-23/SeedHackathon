import { useRef, useEffect } from 'react';
import ActionBadge from './ActionBadge';
import { useLanguage } from '../LanguageContext';

export default function QueryTicker({ queries, connected }) {
  const { t } = useLanguage();
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [queries]);

  return (
    <div style={{
      background: '#07071a', border: '1px solid #1a1a2e', padding: '20px',
      height: '320px', display: 'flex', flexDirection: 'column', borderRadius: '8px',
    }}>
      <div style={{ marginBottom: '4px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '12px', color: '#fff', fontWeight: 500 }}>{t('live_title')}</div>
          <div style={{ fontSize: '11px', letterSpacing: '0.06em', color: connected ? '#555' : '#333' }}>
            {connected ? t('live_status') : t('live_offline')}
          </div>
        </div>
        <div style={{ fontSize: '12px', color: '#444', marginTop: '2px' }}>{t('live_sub')}</div>
      </div>

      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', fontFamily: 'IBM Plex Mono, monospace', fontSize: '12px', marginTop: '12px' }}>
        {queries.length === 0 ? (
          <div style={{ color: '#2a2a2a', paddingTop: '32px', textAlign: 'center', fontSize: '13px', fontFamily: 'inherit' }}>
            {t('live_waiting')}
          </div>
        ) : (
          queries.map((q, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '82px 68px 1fr 72px',
              gap: '0 10px', padding: '3px 0', borderBottom: '1px solid #0f0f0f', alignItems: 'center',
            }}>
              <span style={{ color: '#2a2a2a', fontSize: '11px', whiteSpace: 'nowrap' }}>
                {new Date(q.logged_at || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              <span style={{ color: '#555', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {q.profile_name || q.client_ip}
              </span>
              <span style={{ color: q.action === 'BLOCKED' ? '#444' : '#bbb', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {q.domain}
              </span>
              <ActionBadge action={q.action} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
