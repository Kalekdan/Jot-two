import { useEffect, useRef, useState } from 'react'
import './Dashboard.css'

function StatusBadge({ connected, label, status }) {
  return (
    <div className="status-item">
      <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
      <span className="status-label">{label}</span>
      <span className={`status-text ${connected ? 'connected' : 'disconnected'}`}>
        {status ?? (connected ? 'Running' : 'Stopped')}
      </span>
    </div>
  )
}

function StreamCard({ name, data }) {
  return (
    <div className="stream-card">
      <div className="stream-header">
        <span className="stream-name">{name}</span>
        <span className="stream-length">{data.length ?? '—'} messages</span>
      </div>
      {data.recent_sources && data.recent_sources.length > 0 && (
        <div className="stream-sources">
          <span className="label">Sources:</span>
          {data.recent_sources.map((src) => (
            <span key={src} className="badge">{src}</span>
          ))}
        </div>
      )}
      {data.groups && data.groups.length > 0 && (
        <div className="stream-groups">
          <span className="label">Consumer groups:</span>
          {data.groups.map((g) => (
            <div key={g.name} className="group-row">
              <span className="group-name">{g.name}</span>
              <span className="group-meta">
                {g.consumers} consumer{g.consumers !== 1 ? 's' : ''} · {g.pending} pending
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function TableRowExpander({ table, refreshKey }) {
  const [expanded, setExpanded] = useState(false)
  const [tableData, setTableData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const abortRef = useRef(null)

  async function loadRows() {
    // Cancel any in-flight request before starting a new one
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    try {
      const res = await fetch(`/api/database/${encodeURIComponent(table.name)}/rows`, {
        signal: controller.signal,
      })
      const data = await res.json()
      if (data.ok) {
        setTableData(data)
        setError(null)
      } else {
        setError(data.error ?? 'Failed to load rows')
      }
    } catch (err) {
      if (err.name !== 'AbortError') setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function handleToggle() {
    setExpanded((prev) => !prev)
  }

  useEffect(() => {
    if (expanded) loadRows()
  }, [refreshKey, expanded])

  return (
    <>
      <tr
        className="table-summary-row"
        onClick={handleToggle}
        title={expanded ? 'Collapse' : 'Click to expand rows'}
      >
        <td className="table-name">
          <span className="expand-icon">{expanded ? '▾' : '▸'}</span>
          {table.name}
        </td>
        <td className="table-count">
          {table.row_count >= 0 ? table.row_count.toLocaleString() : '—'}
        </td>
      </tr>
      {expanded && (
        <tr className="table-detail-row">
          <td colSpan={2} className="table-detail-cell">
            {loading && <div className="inline-spinner" />}
            {error && <p className="error-text">{error}</p>}
            {tableData && tableData.rows.length === 0 && (
              <p className="empty-text">Table is empty.</p>
            )}
            {tableData && tableData.rows.length > 0 && (
              <div className="inner-table-wrapper">
                <table className="inner-table">
                  <thead>
                    <tr>
                      {tableData.columns.map((col) => (
                        <th key={col}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableData.rows.map((row, i) => (
                      <tr key={i}>
                        {row.map((cell, j) => (
                          <td key={j}>{cell === null ? <em className="null-val">null</em> : String(cell)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {tableData.rows.length === 50 && (
                  <p className="table-limit-note">Showing first 50 rows.</p>
                )}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

export default function Dashboard() {
  const [streams, setStreams] = useState(null)
  const [database, setDatabase] = useState(null)
  const [serviceStatus, setServiceStatus] = useState(null)
  const [containers, setContainers] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastRefresh, setLastRefresh] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)

  async function fetchAll() {
    try {
      const [streamsRes, dbRes, statusRes, containersRes] = await Promise.all([
        fetch('/api/streams'),
        fetch('/api/database'),
        fetch('/api/status'),
        fetch('/api/containers'),
      ])
      const [streamsData, dbData, statusData, containersData] = await Promise.all([
        streamsRes.json(),
        dbRes.json(),
        statusRes.json(),
        containersRes.json(),
      ])
      setStreams(streamsData)
      setDatabase(dbData)
      setServiceStatus(statusData)
      setContainers(containersData)
      setLastRefresh(new Date())
      setRefreshKey((k) => k + 1)
      setError(null)
    } catch (err) {
      setError(`Failed to load dashboard data: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 10000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner" />
        <p>Loading dashboard…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="dashboard-error">
        <p>{error}</p>
        <button onClick={fetchAll} className="btn-retry">Retry</button>
      </div>
    )
  }

  const streamEntries = streams?.streams ? Object.entries(streams.streams) : []
  const tables = database?.tables ?? []
  const status = serviceStatus?.status ?? {}
  const containerList = containers?.containers ?? []

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1 className="page-title">Dashboard</h1>
        <div className="refresh-row">
          {lastRefresh && (
            <span className="last-refresh">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button onClick={fetchAll} className="btn-refresh">↻ Refresh</button>
        </div>
      </div>

      {/* Service Status */}
      <section className="card">
        <h2 className="card-title">Service Status</h2>
        <div className="status-section-label">Infrastructure</div>
        <div className="status-grid">
          <StatusBadge
            connected={status.redis?.connected ?? false}
            label="Redis"
            status={status.redis?.connected ? 'Connected' : 'Disconnected'}
          />
          <StatusBadge
            connected={status.postgres?.connected ?? false}
            label="PostgreSQL"
            status={status.postgres?.connected ? 'Connected' : 'Disconnected'}
          />
        </div>
        {(status.redis?.error || status.postgres?.error) && (
          <div className="error-details">
            {status.redis?.error && (
              <p className="error-text">Redis: {status.redis.error}</p>
            )}
            {status.postgres?.error && (
              <p className="error-text">PostgreSQL: {status.postgres.error}</p>
            )}
          </div>
        )}

        {/* Docker Containers */}
        {containers?.ok === false ? (
          <div className="containers-unavailable">
            <div className="status-section-label" style={{ marginTop: '1rem' }}>Docker Containers</div>
            <p className="empty-text">Container status unavailable: {containers.error}</p>
          </div>
        ) : containerList.length > 0 && (
          <>
            <div className="status-section-label" style={{ marginTop: '1rem' }}>Docker Containers</div>
            <div className="status-grid">
              {containerList.map((c) => (
                <StatusBadge
                  key={c.id}
                  connected={c.running}
                  label={c.name}
                  status={c.status}
                />
              ))}
            </div>
          </>
        )}
      </section>

      {/* Redis Streams */}
      <section className="card">
        <h2 className="card-title">Redis Streams</h2>
        {streams?.ok === false && (
          <p className="error-text">Could not load streams: {streams.error}</p>
        )}
        {streamEntries.length === 0 && streams?.ok !== false && (
          <p className="empty-text">No streams found.</p>
        )}
        <div className="streams-grid">
          {streamEntries.map(([name, data]) => (
            <StreamCard key={name} name={name} data={data} />
          ))}
        </div>
      </section>

      {/* PostgreSQL Tables */}
      <section className="card">
        <h2 className="card-title">PostgreSQL Tables</h2>
        {database?.ok === false && (
          <p className="error-text">Could not load tables: {database.error}</p>
        )}
        {tables.length === 0 && database?.ok !== false && (
          <p className="empty-text">No tables found.</p>
        )}
        {tables.length > 0 && (
          <div className="table-wrapper">
            <table className="db-table">
              <thead>
                <tr>
                  <th>Table Name</th>
                  <th>Row Count</th>
                </tr>
              </thead>
              <tbody>
                {tables.map((t) => (
                  <TableRowExpander key={t.name} table={t} refreshKey={refreshKey} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
