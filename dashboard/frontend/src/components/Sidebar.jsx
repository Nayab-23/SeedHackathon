import { NavLink } from 'react-router-dom';
import { LayoutDashboard, ShieldX, Users, ScrollText } from 'lucide-react';
import { useLanguage } from '../LanguageContext';

export default function Sidebar() {
  const { t } = useLanguage();

  const navItems = [
    { to: '/', icon: LayoutDashboard, labelKey: 'nav_today' },
    { to: '/lists', icon: ShieldX, labelKey: 'nav_lists' },
    { to: '/profiles', icon: Users, labelKey: 'nav_profiles' },
    { to: '/queries', icon: ScrollText, labelKey: 'nav_queries' },
  ];

  return (
    <aside style={{
      display: 'flex', flexDirection: 'column', height: '100%', width: '248px',
      background: '#07071a', borderRight: '1px solid #1a1a2e',
      overflowX: 'hidden',
    }}>
      <nav style={{ flex: 1, padding: '12px 0' }}>
        {navItems.map(({ to, icon: Icon, labelKey }) => (
          <NavLink key={to} to={to} end={to === '/'}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '10px 18px', fontSize: '14px', textDecoration: 'none',
              color: isActive ? '#fff' : '#4a4a6a',
              background: isActive ? 'rgba(99,102,241,0.12)' : 'transparent',
              borderLeft: `3px solid ${isActive ? '#6366f1' : 'transparent'}`,
              transition: 'all 0.15s',
              whiteSpace: 'nowrap',
            })}
            onMouseEnter={e => { if (!e.currentTarget.dataset.active) e.currentTarget.style.color = '#9090b0'; }}
            onMouseLeave={e => { if (!e.currentTarget.dataset.active) e.currentTarget.style.color = '#4a4a6a'; }}
          >
            {({ isActive }) => (
              <>
                <Icon size={16} style={{ color: isActive ? '#6366f1' : '#4a4a6a', flexShrink: 0 }} />
                <span>{t(labelKey)}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div style={{ padding: '14px 18px', borderTop: '1px solid #1a1a2e' }}>
        <div style={{ fontSize: '11px', color: '#252540', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          {t('nav_footer')}
        </div>
      </div>
    </aside>
  );
}
