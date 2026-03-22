export default function StatCard({ label, value, subValue, accent = '#6366f1' }) {
  return (
    <div style={{
      background: '#07071a',
      border: '1px solid #1a1a2e',
      borderTop: `3px solid ${accent}`,
      padding: '20px 24px',
    }}>
      <div style={{ fontSize: '11px', color: '#4a4a6a', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '10px' }}>
        {label}
      </div>
      <div style={{ fontSize: '36px', fontWeight: 700, letterSpacing: '-0.02em', color: '#fff', lineHeight: 1 }}>
        {value}
      </div>
      {subValue && (
        <div style={{ fontSize: '12px', color: '#4a4a6a', marginTop: '7px' }}>
          {subValue}
        </div>
      )}
    </div>
  );
}
