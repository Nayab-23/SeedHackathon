import { useState, useEffect, useCallback } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { apiFetch } from '../api';
import useWebSocket from '../hooks/useWebSocket';
import StatCard from '../components/StatCard';
import QueryTicker from '../components/QueryTicker';
import { useLanguage } from '../LanguageContext';

const SOFT_RED = '#c07878';

const tooltipStyle = {
  contentStyle: {
    background: '#0c0c0c', border: '1px solid #1e1e1e', borderRadius: 0,
    fontSize: '12px', color: '#888', fontFamily: 'IBM Plex Mono, monospace',
  },
  cursor: { fill: 'rgba(255,255,255,0.02)' },
};

const axisTick = { fill: '#2a2a4a', fontSize: 10, fontFamily: 'IBM Plex Mono, monospace' };

export default function Overview() {
  const { t } = useLanguage();
  const [stats, setStats] = useState(null);
  const [hourly, setHourly] = useState([]);
  const [topBlocked, setTopBlocked] = useState([]);
  const [liveQueries, setLiveQueries] = useState([]);

  const onWsMessage = useCallback((msg) => {
    if (msg.type === 'query') {
      setLiveQueries(prev => [...prev.slice(-99), msg.data]);
    }
  }, []);
  const { connected } = useWebSocket(onWsMessage);

  useEffect(() => {
    Promise.all([
      apiFetch('/stats/overview'),
      apiFetch('/stats/hourly'),
      apiFetch('/stats/top_blocked?limit=10'),
    ]).then(([s, h, tb]) => {
      setStats(s.today || null);
      setHourly(h.hours || []);
      setTopBlocked(tb.domains || []);
    }).catch(() => {});
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>

      <div style={{ marginBottom: '24px' }}>
        <div style={{ fontSize: '17px', fontWeight: 600, color: '#fff' }}>{t('overview_title')}</div>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '12px' }}>
        <StatCard
          label={t('stat_visited')}
          value={stats?.total_queries?.toLocaleString() ?? '—'}
          subValue={t('stat_visited_sub', { n: stats?.allowed?.toLocaleString() ?? '—' })}
          accent="#6366f1"
        />
        <StatCard
          label={t('stat_blocked')}
          value={stats?.blocked?.toLocaleString() ?? '—'}
          subValue={t('stat_blocked_sub', { n: stats?.block_rate ?? '—' })}
          accent={SOFT_RED}
        />
        <StatCard
          label={t('stat_focus')}
          value={0}
          subValue={t('stat_focus_sub')}
          accent="#22c55e"
        />
      </div>

      {/* Live feed + hourly */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
        <QueryTicker queries={liveQueries} connected={connected} />

        <div style={{ background: '#07071a', border: '1px solid #1a1a2e', padding: '20px', borderRadius: '8px' }}>
          <div style={{ fontSize: '12px', color: '#fff', fontWeight: 500, marginBottom: '4px' }}>{t('hourly_title')}</div>
          <div style={{ fontSize: '12px', color: '#444', marginBottom: '16px' }}>{t('hourly_sub')}</div>
          <div style={{ height: '240px' }}>
            {hourly.length === 0 ? (
              <div style={{ color: '#2a2a2a', textAlign: 'center', paddingTop: '80px', fontSize: '13px' }}>{t('no_data')}</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hourly} barCategoryGap="30%">
                  <XAxis dataKey="hour" tick={axisTick} tickFormatter={h => `${h}h`} axisLine={false} tickLine={false} />
                  <YAxis tick={axisTick} axisLine={false} tickLine={false} width={28} />
                  <Tooltip {...tooltipStyle} labelFormatter={h => `${h}:00 – ${h + 1}:00`} formatter={(v, n) => [v, n === 'total' ? 'requests' : 'blocked']} />
                  <Bar dataKey="total" name="total" fill="#6366f1" opacity={0.45} radius={[2,2,0,0]} />
                  <Bar dataKey="blocked" name="blocked" fill={SOFT_RED} opacity={0.75} radius={[2,2,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Top blocked */}
      <div style={{ background: '#07071a', border: '1px solid #1a1a2e', padding: '20px', borderRadius: '8px' }}>
        <div style={{ fontSize: '12px', color: '#fff', fontWeight: 500, marginBottom: '4px' }}>{t('top_blocked_title')}</div>
        <div style={{ fontSize: '12px', color: '#444', marginBottom: '16px' }}>{t('top_blocked_sub')}</div>
        <div style={{ height: '240px' }}>
          {topBlocked.length === 0 ? (
            <div style={{ color: '#2a2a2a', textAlign: 'center', paddingTop: '80px', fontSize: '13px' }}>{t('no_data')}</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topBlocked} layout="vertical" margin={{ left: 0 }}>
                <XAxis type="number" tick={axisTick} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="domain" tick={{ ...axisTick, fill: '#4a4a6a' }} width={130} axisLine={false} tickLine={false} />
                <Tooltip {...tooltipStyle} formatter={v => [v, 'times blocked']} />
                <Bar dataKey="count" name="blocked" radius={[0,2,2,0]}>
                  {topBlocked.map((_, i) => (
                    <Cell key={i} fill={i === 0 ? SOFT_RED : i < 3 ? '#b08888' : '#6366f1'} opacity={i === 0 ? 0.9 : i < 3 ? 0.6 : 0.35} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
