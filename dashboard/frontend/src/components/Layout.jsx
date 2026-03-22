import { useState, useRef, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { PanelLeftOpen, PanelLeftClose, Globe } from 'lucide-react';
import { useLanguage } from '../LanguageContext';
import { LANGUAGES } from '../translations';

export default function Layout() {
  const [open, setOpen] = useState(true);
  const [langOpen, setLangOpen] = useState(false);
  const { lang, setLang, t } = useLanguage();
  const langRef = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (langRef.current && !langRef.current.contains(e.target)) setLangOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const currentLang = LANGUAGES.find(l => l.code === lang) || LANGUAGES[0];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: '#050508' }}>

      {/* Top bar — always visible */}
      <header style={{
        display: 'flex', alignItems: 'center', gap: '12px',
        padding: '0 16px', height: '48px', flexShrink: 0,
        borderBottom: '1px solid #1a1a2e',
        background: '#07071a',
        zIndex: 50,
      }}>
        <button
          onClick={() => setOpen(o => !o)}
          style={{
            background: 'none', border: 'none', cursor: 'pointer', padding: '6px',
            color: open ? '#6366f1' : '#555', transition: 'color 0.15s', lineHeight: 0,
          }}
          title={open ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {open ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
        </button>

        <span style={{ fontSize: '18px', fontWeight: 700, letterSpacing: '-0.03em', color: '#fff' }}>
          flttr
        </span>
        <span style={{ fontSize: '12px', color: '#333', letterSpacing: '0.06em', textTransform: 'uppercase', marginLeft: '2px', marginTop: '2px' }}>
          family filter
        </span>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Language picker */}
        <div ref={langRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setLangOpen(o => !o)}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              background: 'none', border: '1px solid #1a1a2e', cursor: 'pointer',
              padding: '5px 10px', color: '#888', fontSize: '12px',
              borderRadius: '4px', transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = '#333'; e.currentTarget.style.color = '#ccc'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#1a1a2e'; e.currentTarget.style.color = '#888'; }}
          >
            <Globe size={13} />
            <span>{currentLang.native}</span>
          </button>

          {langOpen && (
            <div style={{
              position: 'absolute', top: 'calc(100% + 6px)', right: 0,
              background: '#0c0c1a', border: '1px solid #1a1a2e',
              minWidth: '160px', zIndex: 100, borderRadius: '4px',
              overflow: 'hidden',
              boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
            }}>
              {LANGUAGES.map(l => (
                <button
                  key={l.code}
                  onClick={() => { if (!l.wip) { setLang(l.code); } setLangOpen(false); }}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    width: '100%', background: 'none', border: 'none',
                    padding: '9px 14px', fontSize: '13px', cursor: l.wip ? 'default' : 'pointer',
                    color: lang === l.code ? '#fff' : l.wip ? '#333' : '#888',
                    borderBottom: '1px solid #111',
                    transition: 'background 0.1s',
                    textAlign: 'left',
                  }}
                  onMouseEnter={e => { if (!l.wip) e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'none'; }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {lang === l.code && <span style={{ color: '#6366f1', fontSize: '11px' }}>✓</span>}
                    {lang !== l.code && <span style={{ display: 'inline-block', width: '14px' }} />}
                    {l.native}
                  </span>
                  {l.wip && (
                    <span style={{ fontSize: '10px', color: '#2a2a3a', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                      {t('wip')}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      {/* Body row */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Mobile overlay */}
        {open && (
          <div
            onClick={() => setOpen(false)}
            style={{ position: 'fixed', inset: 0, top: '48px', background: 'rgba(0,0,0,0.6)', zIndex: 30 }}
            className="lg:hidden"
          />
        )}

        {/* Sidebar */}
        <div style={{
          width: open ? '248px' : '0',
          flexShrink: 0,
          overflow: 'hidden',
          transition: 'width 0.2s cubic-bezier(0.4,0,0.2,1)',
          position: 'relative',
          zIndex: 40,
        }}>
          <Sidebar onClose={() => setOpen(false)} />
        </div>

        {/* Main content */}
        <main style={{
          flex: 1, overflowY: 'auto', padding: '32px',
          minWidth: 0,
          transition: 'padding 0.2s',
        }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
