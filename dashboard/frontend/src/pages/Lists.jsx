import { useState, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { apiFetch, apiUpload } from '../api';
import DomainTable from '../components/DomainTable';
import AddDomainModal from '../components/AddDomainModal';
import BulkImportModal from '../components/BulkImportModal';
import ConfirmDialog from '../components/ConfirmDialog';
import { useLanguage } from '../LanguageContext';

const PER_PAGE = 50;

export default function Lists() {
  const { t } = useLanguage();
  const TABS = [
    { key: 'blacklist', labelKey: 'tab_blacklist', descKey: 'tab_blacklist_desc' },
    { key: 'whitelist', labelKey: 'tab_whitelist', descKey: 'tab_whitelist_desc' },
  ];

  const [tab, setTab] = useState('blacklist');
  const [domains, setDomains] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState('added_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [showBulk, setShowBulk] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const currentTab = TABS.find(tb => tb.key === tab);

  const fetchDomains = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: String(PER_PAGE), sort: sortField, order: sortOrder });
      if (search) params.set('search', search);
      const data = await apiFetch(`/lists/${tab}?${params}`);
      setDomains(data.domains || []);
      setTotal(data.total || 0);
      setPages(data.pages || 1);
    } catch {
      setDomains([]);
    } finally { setLoading(false); }
  }, [tab, page, search, sortField, sortOrder]);

  useEffect(() => { fetchDomains(); }, [fetchDomains]);
  useEffect(() => { setPage(1); }, [tab, search]);

  function handleSort(field) {
    if (sortField === field) setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortOrder('asc'); }
  }

  async function handleAddDomain({ domain, reason }) {
    await apiFetch(`/lists/${tab}`, { method: 'POST', body: JSON.stringify({ domain, reason }) });
    fetchDomains();
  }

  async function handleBulkText({ domains: list, reason }) {
    const res = await apiFetch(`/lists/${tab}/bulk`, { method: 'POST', body: JSON.stringify({ domains: list, reason }) });
    fetchDomains();
    return res;
  }

  async function handleBulkFile(file) {
    const res = await apiUpload(`/lists/${tab}/import`, file);
    fetchDomains();
    return res;
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    await apiFetch(`/lists/${tab}/${encodeURIComponent(deleteTarget.domain)}`, { method: 'DELETE' });
    setDeleteTarget(null);
    fetchDomains();
  }

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <div style={{ fontSize: '17px', fontWeight: 600, color: '#fff', marginBottom: '4px' }}>{t('lists_title')}</div>
        <div style={{ fontSize: '13px', color: '#444' }}>{t('lists_sub')}</div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #1e1e1e', marginBottom: '20px' }}>
        {TABS.map(tb => (
          <button key={tb.key} onClick={() => setTab(tb.key)} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            padding: '10px 20px', fontSize: '14px',
            color: tab === tb.key ? '#fff' : '#444',
            borderBottom: `2px solid ${tab === tb.key ? '#fff' : 'transparent'}`,
            marginBottom: '-1px', transition: 'color 0.1s',
          }}>
            {t(tb.labelKey)}
            {tab === tb.key && total > 0 && (
              <span style={{ marginLeft: '8px', color: '#333', fontSize: '11px' }}>{total}</span>
            )}
          </button>
        ))}
      </div>

      <div style={{ fontSize: '13px', color: '#444', marginBottom: '16px' }}>{t(currentTab.descKey)}</div>

      {/* Toolbar */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px', alignItems: 'center' }}>
        <input
          type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder={t('search_placeholder')}
          style={{ flex: '1', minWidth: '160px', maxWidth: '300px' }}
        />
        <button onClick={() => setShowAdd(true)} className="btn-primary">{t('btn_add')}</button>
        <button onClick={() => setShowBulk(true)} className="btn-secondary">{t('btn_import')}</button>
      </div>

      <div style={{ background: '#0c0c0c', border: '1px solid #1e1e1e' }}>
        <DomainTable
          domains={domains} sortField={sortField} sortOrder={sortOrder}
          onSort={handleSort} onDelete={d => setDeleteTarget(d)} loading={loading}
        />
        {pages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 16px', borderTop: '1px solid #1e1e1e' }}>
            <span style={{ fontSize: '12px', color: '#444' }}>{t('pagination', { p: page, t: pages, n: total })}</span>
            <div style={{ display: 'flex', gap: '4px' }}>
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} className="btn"><ChevronLeft size={13} /></button>
              <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page >= pages} className="btn"><ChevronRight size={13} /></button>
            </div>
          </div>
        )}
      </div>

      <AddDomainModal open={showAdd} listType={t(currentTab.labelKey)} onAdd={handleAddDomain} onClose={() => setShowAdd(false)} />
      <BulkImportModal open={showBulk} listType={t(currentTab.labelKey)} onImportText={handleBulkText} onImportFile={handleBulkFile} onClose={() => setShowBulk(false)} />
      <ConfirmDialog
        open={!!deleteTarget}
        title={t('confirm_remove_title')}
        message={t('confirm_remove_msg', { domain: deleteTarget?.domain, list: t(currentTab.labelKey).toLowerCase() })}
        confirmLabel={t('btn_remove')}
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
