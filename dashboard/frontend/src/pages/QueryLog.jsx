import { useState, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight, ChevronUp, ChevronDown } from 'lucide-react';
import { apiFetch } from '../api';
import ActionBadge from '../components/ActionBadge';
import { useSearchParams } from 'react-router-dom';
import { useLanguage } from '../LanguageContext';

const PER_PAGE = 100;

const th = {
  padding: '10px 14px', textAlign: 'left', fontSize: '11px',
  letterSpacing: '0.1em', textTransform: 'uppercase', color: '#444',
  cursor: 'pointer', userSelect: 'none', borderBottom: '1px solid #1e1e1e',
  whiteSpace: 'nowrap', background: '#0c0c0c',
};
const td = { padding: '9px 14px', borderBottom: '1px solid #0f0f0f', fontSize: '13px' };

export default function QueryLog() {
  const { t } = useLanguage();
  const [searchParams, setSearchParams] = useSearchParams();
  const [queries, setQueries] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [profiles, setProfiles] = useState([]);
  const [showFilters, setShowFilters] = useState(false);
  const [profileFilter, setProfileFilter] = useState(searchParams.get('profile') || '');
  const [actionFilter, setActionFilter] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [sortField, setSortField] = useState('logged_at');
  const [sortOrder, setSortOrder] = useState('desc');

  useEffect(() => {
    apiFetch('/profiles').then(d => setProfiles(d.profiles || [])).catch(() => {});
  }, []);

  const fetchQueries = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: String(PER_PAGE) });
      if (profileFilter) params.set('profile_id', profileFilter);
      if (actionFilter) params.set('action', actionFilter);
      if (searchTerm) params.set('search', searchTerm);
      if (dateFrom) params.set('from', new Date(dateFrom).toISOString());
      if (dateTo) params.set('to', new Date(dateTo).toISOString());
      const data = await apiFetch(`/queries?${params}`);
      setQueries(data.queries || []);
      setTotal(data.total || 0);
      setPages(data.pages || 1);
    } catch {
      setQueries([]);
    } finally { setLoading(false); }
  }, [page, profileFilter, actionFilter, searchTerm, dateFrom, dateTo]);

  useEffect(() => { fetchQueries(); }, [fetchQueries]);
  useEffect(() => { setPage(1); }, [profileFilter, actionFilter, searchTerm, dateFrom, dateTo]);

  function handleSort(field) {
    if (sortField === field) setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortOrder('desc'); }
  }

  async function handleExport() {
    const params = new URLSearchParams();
    if (profileFilter) params.set('profile_id', profileFilter);
    if (actionFilter) params.set('action', actionFilter);
    if (searchTerm) params.set('search', searchTerm);
    if (dateFrom) params.set('from', new Date(dateFrom).toISOString());
    if (dateTo) params.set('to', new Date(dateTo).toISOString());
    try {
      const res = await apiFetch(`/queries/export?${params}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `activity-${new Date().toISOString().slice(0, 10)}.csv`; a.click();
      URL.revokeObjectURL(url);
    } catch {}
  }

  function clearFilters() {
    setProfileFilter(''); setActionFilter(''); setSearchTerm('');
    setDateFrom(''); setDateTo(''); setSearchParams({});
  }

  const hasFilters = profileFilter || actionFilter || searchTerm || dateFrom || dateTo;

  const sorted = [...queries].sort((a, b) => {
    const av = a[sortField] || '', bv = b[sortField] || '';
    return sortOrder === 'asc' ? (av < bv ? -1 : av > bv ? 1 : 0) : (av > bv ? -1 : av < bv ? 1 : 0);
  });

  const SortIcon = ({ field }) => {
    if (sortField !== field) return null;
    return sortOrder === 'asc'
      ? <ChevronUp size={11} style={{ display: 'inline', marginLeft: '3px' }} />
      : <ChevronDown size={11} style={{ display: 'inline', marginLeft: '3px' }} />;
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <div>
          <div style={{ fontSize: '17px', fontWeight: 600, color: '#fff', marginBottom: '4px' }}>{t('queries_title')}</div>
          <div style={{ fontSize: '13px', color: '#444' }}>
            {t('queries_sub', { n: total.toLocaleString() })}
          </div>
        </div>
        {total > 0 && (
          <button onClick={handleExport} className="btn-secondary">{t('btn_export')}</button>
        )}
      </div>

      {/* Filters */}
      <div style={{ margin: '16px 0', display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
        <input
          type="text" value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
          placeholder={t('search_placeholder')}
          style={{ flex: '1', minWidth: '160px', maxWidth: '280px' }}
        />
        <button onClick={() => setShowFilters(!showFilters)} className="btn-secondary">
          {hasFilters ? t('filter_active') : t('filter_btn')}
        </button>
        {hasFilters && (
          <button onClick={clearFilters} style={{ background: 'none', border: 'none', color: '#444', cursor: 'pointer', fontSize: '12px' }}>
            {t('clear_filters')}
          </button>
        )}
      </div>

      {showFilters && (
        <div style={{ background: '#0c0c0c', border: '1px solid #1e1e1e', padding: '16px', marginBottom: '16px', display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'flex-end' }}>
          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '6px' }}>{t('filter_child')}</div>
            <select value={profileFilter} onChange={e => setProfileFilter(e.target.value)} style={{ width: 'auto', minWidth: '120px' }}>
              <option value="">{t('filter_all_kids')}</option>
              {profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '6px' }}>{t('filter_result')}</div>
            <select value={actionFilter} onChange={e => setActionFilter(e.target.value)} style={{ width: 'auto', minWidth: '120px' }}>
              <option value="">{t('filter_all')}</option>
              <option value="ALLOWED">{t('filter_allowed')}</option>
              <option value="BLOCKED">{t('filter_blocked')}</option>
              <option value="WHITELISTED">{t('filter_whitelisted')}</option>
            </select>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '6px' }}>{t('filter_from')}</div>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} style={{ width: 'auto' }} />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#444', marginBottom: '6px' }}>{t('filter_to')}</div>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} style={{ width: 'auto' }} />
          </div>
        </div>
      )}

      {/* Table */}
      <div style={{ background: '#0c0c0c', border: '1px solid #1e1e1e' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={th} onClick={() => handleSort('logged_at')}>{t('col_time')} <SortIcon field="logged_at" /></th>
                <th style={{ ...th, display: 'none' }} className="sm:table-cell" onClick={() => handleSort('profile_name')}>{t('col_who')} <SortIcon field="profile_name" /></th>
                <th style={th} onClick={() => handleSort('domain')}>{t('col_website') || 'Website'} <SortIcon field="domain" /></th>
                <th style={{ ...th, display: 'none' }} className="md:table-cell">{t('col_type')}</th>
                <th style={th} onClick={() => handleSort('action')}>{t('col_result')} <SortIcon field="action" /></th>
                <th style={{ ...th, display: 'none' }} className="lg:table-cell">{t('col_speed')}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} style={{ ...td, color: '#2a2a2a', textAlign: 'center', padding: '40px' }}>{t('loading')}</td></tr>
              ) : sorted.length === 0 ? (
                <tr><td colSpan={6} style={{ ...td, color: '#2a2a2a', textAlign: 'center', padding: '40px' }}>{t('no_activity')}</td></tr>
              ) : (
                sorted.map(q => (
                  <tr key={q.id}
                    onMouseEnter={e => e.currentTarget.style.background = '#0f0f0f'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}
                    style={{ transition: 'background 0.1s' }}
                  >
                    <td style={{ ...td, color: '#333', fontSize: '12px', fontFamily: 'IBM Plex Mono, monospace', whiteSpace: 'nowrap' }}>
                      {new Date(q.logged_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td style={{ ...td, color: '#777', display: 'none' }} className="sm:table-cell">
                      {q.profile_name || <span style={{ color: '#2a2a2a', fontFamily: 'IBM Plex Mono, monospace', fontSize: '12px' }}>{q.client_ip}</span>}
                    </td>
                    <td style={{ ...td, color: q.action === 'BLOCKED' ? '#444' : '#ccc', fontFamily: 'IBM Plex Mono, monospace', maxWidth: '260px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {q.domain}
                    </td>
                    <td style={{ ...td, color: '#333', fontSize: '12px', display: 'none' }} className="md:table-cell">{q.query_type}</td>
                    <td style={td}><ActionBadge action={q.action} /></td>
                    <td style={{ ...td, color: '#2a2a2a', fontSize: '12px', fontVariantNumeric: 'tabular-nums', display: 'none' }} className="lg:table-cell">
                      {q.response_ms != null ? `${q.response_ms.toFixed(1)}ms` : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {pages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderTop: '1px solid #1e1e1e' }}>
            <span style={{ fontSize: '12px', color: '#333' }}>{t('page_of', { p: page, t: pages })}</span>
            <div style={{ display: 'flex', gap: '4px' }}>
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} className="btn"><ChevronLeft size={13} /></button>
              {Array.from({ length: Math.min(5, pages) }, (_, i) => {
                const start = Math.max(1, Math.min(page - 2, pages - 4));
                const n = start + i;
                if (n > pages) return null;
                return (
                  <button key={n} onClick={() => setPage(n)} className="btn"
                    style={{ color: page === n ? '#fff' : '#444', borderColor: page === n ? '#333' : '#1e1e1e' }}>
                    {n}
                  </button>
                );
              })}
              <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page >= pages} className="btn"><ChevronRight size={13} /></button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
