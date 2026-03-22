import { useState, useEffect } from 'react';
import { Plus, Trash2, ChevronRight } from 'lucide-react';
import { apiFetch } from '../api';
import FocusTimer from '../components/FocusTimer';
import CreateProfileModal from '../components/CreateProfileModal';
import SetFocusModal from '../components/SetFocusModal';
import ConfirmDialog from '../components/ConfirmDialog';
import { useNavigate } from 'react-router-dom';
import { useLanguage } from '../LanguageContext';

const row = { display: 'flex', alignItems: 'center', justifyContent: 'space-between' };
const iconBtn = { background: 'none', border: 'none', color: '#333', cursor: 'pointer', padding: '4px', transition: 'color 0.1s', lineHeight: 1 };

export default function Profiles() {
  const { t } = useLanguage();
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [focusTarget, setFocusTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [addDeviceId, setAddDeviceId] = useState(null);
  const [newIp, setNewIp] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const navigate = useNavigate();

  async function fetchProfiles() {
    setLoading(true);
    try {
      const data = await apiFetch('/profiles');
      setProfiles(data.profiles || []);
    } catch {
      setProfiles([]);
    } finally { setLoading(false); }
  }

  useEffect(() => { fetchProfiles(); }, []);

  async function handleCreate({ name, device }) {
    const res = await apiFetch('/profiles', { method: 'POST', body: JSON.stringify({ name }) });
    if (device?.ip && res.id) {
      await apiFetch(`/profiles/${res.id}/devices`, { method: 'POST', body: JSON.stringify({ ip: device.ip, label: device.label }) });
    }
    fetchProfiles();
  }

  async function handleAddDevice(profileId) {
    if (!newIp.trim()) return;
    await apiFetch(`/profiles/${profileId}/devices`, { method: 'POST', body: JSON.stringify({ ip: newIp.trim(), label: newLabel.trim() }) });
    setAddDeviceId(null); setNewIp(''); setNewLabel('');
    fetchProfiles();
  }

  async function handleRemoveDevice(profileId, deviceId) {
    await apiFetch(`/profiles/${profileId}/devices/${deviceId}`, { method: 'DELETE' });
    fetchProfiles();
  }

  async function handleSetFocus(profileId, data) {
    await apiFetch('/focus', { method: 'POST', body: JSON.stringify({ profile_id: profileId, ...data }) });
    fetchProfiles();
  }

  async function handleExtendFocus(focusId) {
    await apiFetch(`/focus/${focusId}/extend`, { method: 'PUT', body: JSON.stringify({ extra_minutes: 30 }) });
    fetchProfiles();
  }

  async function handleEndFocus(focusId) {
    await apiFetch(`/focus/${focusId}`, { method: 'DELETE' });
    fetchProfiles();
  }

  async function handleDeleteProfile() {
    if (!deleteTarget) return;
    await apiFetch(`/profiles/${deleteTarget}`, { method: 'DELETE' });
    setDeleteTarget(null);
    fetchProfiles();
  }

  if (loading) {
    return <div style={{ color: '#333', padding: '40px', fontSize: '13px' }}>{t('loading')}</div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <div>
          <div style={{ fontSize: '17px', fontWeight: 600, color: '#fff', marginBottom: '4px' }}>{t('profiles_title')}</div>
          <div style={{ fontSize: '13px', color: '#444' }}>{t('profiles_sub')}</div>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary">{t('btn_add_child')}</button>
      </div>

      {profiles.length === 0 ? (
        <div style={{ marginTop: '48px', textAlign: 'center', color: '#2a2a2a', fontSize: '13px' }}>
          {t('btn_add_child')} to get started
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1px', marginTop: '16px' }}>
          {profiles.map(p => (
            <div key={p.id} style={{ background: '#0c0c0c', border: '1px solid #1e1e1e', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

              {/* Header */}
              <div style={row}>
                <div>
                  <div style={{ fontSize: '20px', fontWeight: 600, letterSpacing: '-0.01em' }}>{p.name}</div>
                  {p.stats && (
                    <div style={{ fontSize: '12px', color: '#444', marginTop: '3px' }}>
                      {t('queries_today', { n: p.stats.queries_today.toLocaleString() })} &nbsp;·&nbsp; {t('blocked_today', { n: p.stats.blocked_today })}
                    </div>
                  )}
                </div>
                <button onClick={() => setDeleteTarget(p.id)} style={iconBtn}
                  onMouseEnter={e => e.currentTarget.style.color = '#888'}
                  onMouseLeave={e => e.currentTarget.style.color = '#333'}>
                  <Trash2 size={14} />
                </button>
              </div>

              {/* Active Focus */}
              {p.active_focus ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '11px', color: '#444', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                    {t('focus_active')}
                  </div>
                  <FocusTimer expiresAt={p.active_focus.expires_at} note={p.active_focus.note} strictness={p.active_focus.strictness} />
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button onClick={() => handleExtendFocus(p.active_focus.id)} className="btn-secondary">{t('btn_extend')}</button>
                    <button onClick={() => handleEndFocus(p.active_focus.id)} className="btn-danger">{t('btn_end_session')}</button>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: '13px', color: '#2a2a2a', fontStyle: 'italic' }}>
                  {t('no_focus')}
                </div>
              )}

              {/* Devices */}
              <div>
                <div style={{ ...row, marginBottom: '8px' }}>
                  <div style={{ fontSize: '11px', color: '#444', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{t('devices_label')}</div>
                  <button onClick={() => setAddDeviceId(addDeviceId === p.id ? null : p.id)} style={iconBtn}
                    onMouseEnter={e => e.currentTarget.style.color = '#888'}
                    onMouseLeave={e => e.currentTarget.style.color = '#333'}>
                    <Plus size={13} />
                  </button>
                </div>

                {p.devices?.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    {p.devices.map(d => (
                      <div key={d.id} style={{ ...row, padding: '6px 0', borderBottom: '1px solid #111' }}>
                        <div>
                          <span style={{ fontSize: '13px', color: '#888' }}>{d.label || 'Device'}</span>
                          <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: '11px', color: '#333', marginLeft: '8px' }}>{d.ip}</span>
                        </div>
                        <button onClick={() => handleRemoveDevice(p.id, d.id)} style={iconBtn}
                          onMouseEnter={e => e.currentTarget.style.color = '#888'}
                          onMouseLeave={e => e.currentTarget.style.color = '#333'}>
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: '12px', color: '#2a2a2a' }}>{t('no_devices')}</div>
                )}

                {addDeviceId === p.id && (
                  <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
                    <input type="text" value={newIp} onChange={e => setNewIp(e.target.value)} placeholder={t('ip_placeholder')} style={{ flex: 1 }} />
                    <input type="text" value={newLabel} onChange={e => setNewLabel(e.target.value)} placeholder={t('label_placeholder')} style={{ flex: 1 }} />
                    <button onClick={() => handleAddDevice(p.id)} className="btn-primary">{t('btn_add_device')}</button>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingTop: '4px', borderTop: '1px solid #111' }}>
                {!p.active_focus && (
                  <button onClick={() => setFocusTarget(p)} className="btn-secondary">{t('btn_set_focus')}</button>
                )}
                <button
                  onClick={() => navigate(`/queries?profile=${p.id}`)}
                  className="btn-secondary"
                  style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  {t('btn_view_activity')} <ChevronRight size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <CreateProfileModal open={showCreate} onClose={() => setShowCreate(false)} onCreate={handleCreate} />
      {focusTarget && (
        <SetFocusModal open profileName={focusTarget.name} onClose={() => setFocusTarget(null)} onSet={data => handleSetFocus(focusTarget.id, data)} />
      )}
      <ConfirmDialog
        open={!!deleteTarget}
        title={t('delete_profile_title')}
        message={t('delete_profile_msg')}
        confirmLabel={t('btn_delete')}
        danger
        onConfirm={handleDeleteProfile}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
