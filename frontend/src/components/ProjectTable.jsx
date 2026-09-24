import { formatPrice, formatSupply, formatUsdCompact } from '../utils/format.js';

const COLUMNS = [
  { key: 'project', label: 'Project' },
  { key: 'current_price', label: 'Price', numeric: true },
  { key: 'market_cap', label: 'Market cap', numeric: true },
  { key: 'fully_diluted_valuation', label: 'FDV', numeric: true },
  { key: 'total_volume', label: '24h volume', numeric: true },
  { key: 'tvl_usd', label: 'TVL', numeric: true },
  { key: 'total_supply', label: 'Supply (max = total)', numeric: true },
];

export default function ProjectTable({ projects, sortBy, emptyMessage }) {
  return (
    <div className="table-wrap">
      <table className="projects">
        <thead>
          <tr>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={[col.numeric ? 'numeric' : '', col.key === sortBy ? 'sorted' : ''].join(' ')}
                aria-sort={col.key === sortBy ? 'other' : undefined}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {projects.length === 0 && (
            <tr>
              <td colSpan={COLUMNS.length} className="empty">
                {emptyMessage}
              </td>
            </tr>
          )}
          {projects.map((p) => (
            <tr key={p.id}>
              <td>
                <div className="project-cell">
                  {p.image ? <img src={p.image} alt="" width="24" height="24" loading="lazy" /> : <span className="logo-placeholder" />}
                  <div>
                    <div className="project-name">{p.name}</div>
                    <div className="project-symbol">
                      {p.symbol.toUpperCase()}
                      {p.market_cap_rank != null && ` #${p.market_cap_rank}`}
                    </div>
                  </div>
                </div>
              </td>
              <td className="numeric">{formatPrice(p.current_price)}</td>
              <td className={sortBy === 'market_cap' ? 'numeric sorted' : 'numeric'}>{formatUsdCompact(p.market_cap)}</td>
              <td className="numeric">{formatUsdCompact(p.fully_diluted_valuation)}</td>
              <td className={sortBy === 'total_volume' ? 'numeric sorted' : 'numeric'}>{formatUsdCompact(p.total_volume)}</td>
              <td className="numeric">{formatUsdCompact(p.tvl_usd)}</td>
              <td className="numeric">{formatSupply(p.total_supply)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
