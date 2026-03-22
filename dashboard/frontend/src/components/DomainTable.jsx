import { ChevronUp, ChevronDown } from 'lucide-react';

const th = {
  padding: '10px 16px',
  textAlign: 'left',
  fontSize: '11px',
  letterSpacing: '0.1em',
  textTransform: 'uppercase',
  color: '#444',
  cursor: 'pointer',
  userSelect: 'none',
  borderBottom: '1px solid #1e1e1e',
  whiteSpace: 'nowrap',
};

const td = {
  padding: '10px 16px',
  borderBottom: '1px solid #0f0f0f',
  fontSize: '13px',
};

export default function DomainTable({ domains, sortField, sortOrder, onSort, onDelete, loading }) {
  const SortIcon = ({ field }) => {
    if (sortField !== field) return null;
    return sortOrder === 'asc'
      ? <ChevronUp size={12} style={{ display: 'inline', marginLeft: '4px', color: '#888' }} />
      : <ChevronDown size={12} style={{ display: 'inline', marginLeft: '4px', color: '#888' }} />;
  };

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={th} onClick={() => onSort('domain')}>Website <SortIcon field="domain" /></th>
            <th style={{ ...th, display: 'none' }} className="sm:table-cell" onClick={() => onSort('added_by')}>Added By <SortIcon field="added_by" /></th>
            <th style={{ ...th, display: 'none' }} className="md:table-cell">Reason</th>
            <th style={th} onClick={() => onSort('added_at')}>Date Added <SortIcon field="added_at" /></th>
            <th style={{ ...th, width: '40px' }}></th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={5} style={{ ...td, color: '#333', textAlign: 'center', padding: '40px' }}>loading...</td>
            </tr>
          ) : domains.length === 0 ? (
            <tr>
              <td colSpan={5} style={{ ...td, color: '#333', textAlign: 'center', padding: '40px' }}>no domains</td>
            </tr>
          ) : (
            domains.map((d) => (
              <tr key={d.id} style={{ transition: 'background 0.1s' }}
                onMouseEnter={e => e.currentTarget.style.background = '#0f0f0f'}
                onMouseLeave={e => e.currentTarget.style.background = ''}
              >
                <td style={{ ...td, color: '#ccc', fontFamily: 'IBM Plex Mono, monospace' }}>{d.domain}</td>
                <td style={{ ...td, color: '#555', display: 'none' }} className="sm:table-cell">{d.added_by}</td>
                <td style={{ ...td, color: '#444', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'none' }} className="md:table-cell">
                  {d.reason || '—'}
                </td>
                <td style={{ ...td, color: '#333', whiteSpace: 'nowrap', fontSize: '12px' }}>
                  {new Date(d.added_at).toLocaleDateString()}
                </td>
                <td style={td}>
                  <button
                    onClick={() => onDelete(d)}
                    style={{
                      background: 'none', border: 'none', color: '#2a2a2a',
                      cursor: 'pointer', fontSize: '15px', lineHeight: 1,
                      padding: '2px 6px', transition: 'color 0.1s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.color = '#888'}
                    onMouseLeave={e => e.currentTarget.style.color = '#2a2a2a'}
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
