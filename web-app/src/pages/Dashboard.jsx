import { useEffect, useState } from 'react'
import './Dashboard.css'

function StatusBadge({ connected, label }) {
  return (
    <div className="status-item">
      <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
      <span className="status-label">{label}</span>
      <span className={`status-text ${connected ? 'connected' : 'disconnected'}`}>
        {connected ? 'Connected' : 'Disconnected'}
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

function TableRow({ table }) {
  return (
    <tr>
      <td className="table-name">{table.name}</td>
      <td className="table-count">{table.row_count >= 0 ? table.row_count.toLocaleString() : '—'}</td>
    </tr>
  )
}

export default function Dashboard() {
  const [streams, setStreams] = useState(null)
  const [database, setDatabase] = useState(null)
  const [serviceStatus, setServiceStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastRefresh, setLastRefresh] = useState(null)

  async function fetchAll() {
    try {
      const [streamsRes, dbRes, statusRes] = await Promise.all([
        fetch('/api/streams'),
        fetch('/api/database'),
        fetch('/api/status'),
      ])
      const [streamsData, dbData, statusData] = await Promise.all([
        streamsRes.json(),
        dbRes.json(),
        statusRes.json(),
      ])
      setStreams(streamsData)
      setDatabase(dbData)
      setServiceStatus(statusData)
      setLastRefresh(new Date())
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
        <div className="status-grid">
          <StatusBadge
            connected={status.redis?.connected ?? false}
            label="Redis"
          />
          <StatusBadge
            connected={status.postgres?.connected ?? false}
            label="PostgreSQL"
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
                  <TableRow key={t.name} table={t} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
