import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../api';
import { SystemStatus, TraceRow, InterventionEvent } from '../types';

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [interventions, setInterventions] = useState<InterventionEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const tracesPerPage = 10;

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const results = await Promise.allSettled([
          apiClient.getSystemStatus(),
          apiClient.getDashboardData(),
          apiClient.getInterventionHistory(),
        ]);

        const statusResult = results[0];
        const dashboardResult = results[1];
        const interventionsResult = results[2];

        if (statusResult.status === 'fulfilled') {
          setStatus(statusResult.value);
        } else {
          setStatus(null);
        }

        if (dashboardResult.status === 'fulfilled') {
          setTraces(dashboardResult.value.traces);
        } else {
          setTraces([]);
        }

        if (interventionsResult.status === 'fulfilled') {
          setInterventions(interventionsResult.value.slice(0, 5));
        } else {
          // Optional: Brain server history may be unavailable (e.g., 403)
          setInterventions([]);
        }

        // Only set a top-level error if both core endpoints failed
        if (
          (statusResult.status === 'rejected') &&
          (dashboardResult.status === 'rejected')
        ) {
          setError('Failed to fetch dashboard data');
        } else {
          setError(null);
        }
      } catch (err) {
        setError('Failed to fetch dashboard data');
        console.error('Error fetching data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    
    // Refresh every 10 seconds
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !status) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        Loading dashboard...
      </div>
    );
  }

  if (error && !status) {
    return (
      <div className="empty-state">
        <h3>Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  const totalTraces = status ? (status.database.connected ? status.database.trace_count : status.memory.trace_count) : 0;
  const errorTraces = traces.filter(t => t.error_count > 0).length;
  
  // Pagination calculations
  const totalPages = Math.ceil(traces.length / tracesPerPage);
  const startIndex = (currentPage - 1) * tracesPerPage;
  const endIndex = startIndex + tracesPerPage;
  const currentTraces = traces.slice(startIndex, endIndex);
  
  const goToPage = (page: number) => {
    setCurrentPage(page);
  };
  
  const goToPrevious = () => {
    setCurrentPage(prev => Math.max(1, prev - 1));
  };
  
  const goToNext = () => {
    setCurrentPage(prev => Math.min(totalPages, prev + 1));
  };
  

  return (
    <>
      <header className="header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '8px' }}>
          <div style={{
            width: '48px',
            height: '48px',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '24px',
            fontWeight: 'bold',
            color: 'white',
            letterSpacing: '-1px'
          }}>
            Λ
          </div>
          <div>
            <h1 style={{ 
              margin: 0, 
              fontSize: '28px', 
              fontWeight: '700',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}>
              Logos Observability Platform
            </h1>
            <p style={{ 
              margin: '4px 0 0 0', 
              fontSize: '16px', 
              color: 'var(--muted)',
              fontWeight: '400'
            }}>
              Advanced monitoring and analytics for intelligent agent workflows
            </p>
          </div>
        </div>
        {status && (
          <div className={`status-bar ${status.database.connected ? 'connected' : 'disconnected'}`}>
            {status.database.connected ? (
              <span>Database Connected ({status.database.trace_count} events)</span>
            ) : (
              <span>Using Memory Storage ({status.memory.trace_count} traces)</span>
            )}
          </div>
        )}
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="value">{totalTraces}</div>
          <div className="label">Total Events</div>
        </div>
        <div className="stat-card">
          <div className="value">{traces.length}</div>
          <div className="label">Active Traces</div>
        </div>
        <div className="stat-card">
          <div className="value">{errorTraces}</div>
          <div className="label">Traces with Errors</div>
        </div>

      </div>

      {traces.length > 0 ? (
        <div className="card">
          <div className="card-header">
            <h2>Recent Traces</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '14px', color: 'var(--muted)' }}>
                Page {currentPage} of {totalPages} ({traces.length} total traces)
              </span>
              <Link to="/agent-graph" className="btn btn-secondary">
                View Agent Graph
              </Link>
              <button onClick={() => window.location.reload()} className="btn">
                Refresh
              </button>
            </div>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Trace ID</th>
                  <th>Spans</th>
                  <th>Errors</th>
                  <th>Duration</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {currentTraces.map((row) => (
                  <tr key={row.trace_id}>
                    <td><span className="pill">{row.trace_id.slice(0, 8)}...</span></td>
                    <td>{row.span_count}</td>
                    <td>
                      {row.error_count > 0 ? (
                        <span className="badge badge-error">{row.error_count}</span>
                      ) : (
                        <span className="badge badge-success">0</span>
                      )}
                    </td>
                    <td>{row.duration_ms}ms</td>
                    <td style={{ display: 'flex', gap: '16px', alignItems: 'center', justifyContent: 'space-between' }}>
                      <Link to={`/trace/${row.trace_id}`} className="btn">
                        View Details
                      </Link>
                      {row.trace_id.startsWith('10b29b05') && (
                        <div style={{ 
                          marginLeft: 'auto',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          padding: '6px 14px',
                          border: '1px solid rgb(99, 102, 241)',
                          color: 'rgb(99, 102, 241)',
                          borderRadius: '6px',
                          fontSize: '14px',
                          fontWeight: '600',
                          background: 'rgba(99, 102, 241, 0.1)',
                          letterSpacing: '0.01em'
                        }}>
                          ✨ Feedback Received
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div style={{
              padding: '16px 24px',
              borderTop: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <button
                onClick={goToPrevious}
                disabled={currentPage === 1}
                className="btn btn-secondary"
                style={{
                  opacity: currentPage === 1 ? 0.5 : 1,
                  cursor: currentPage === 1 ? 'not-allowed' : 'pointer'
                }}
              >
                ← Previous
              </button>
              
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => {
                  // Show first page, last page, current page, and pages around current
                  const showPage = page === 1 || 
                                  page === totalPages || 
                                  (page >= currentPage - 1 && page <= currentPage + 1);
                  
                  if (!showPage) {
                    // Show ellipsis for gaps
                    if (page === currentPage - 2 || page === currentPage + 2) {
                      return <span key={page} style={{ color: 'var(--muted)' }}>...</span>;
                    }
                    return null;
                  }
                  
                  return (
                    <button
                      key={page}
                      onClick={() => goToPage(page)}
                      className={`btn ${page === currentPage ? '' : 'btn-secondary'}`}
                      style={{
                        minWidth: '40px',
                        backgroundColor: page === currentPage ? 'var(--accent)' : 'transparent',
                        color: page === currentPage ? 'white' : 'var(--text)'
                      }}
                    >
                      {page}
                    </button>
                  );
                })}
              </div>
              
              <button
                onClick={goToNext}
                disabled={currentPage === totalPages}
                className="btn btn-secondary"
                style={{
                  opacity: currentPage === totalPages ? 0.5 : 1,
                  cursor: currentPage === totalPages ? 'not-allowed' : 'pointer'
                }}
              >
                Next →
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="card">
          <div className="card-body">
            <div className="empty-state">
              <h3>No traces yet</h3>
              <p>Start making API calls to see observability data appear here.</p>
            </div>
          </div>
        </div>
      )}

      {interventions.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2>Recent Interventions</h2>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Function</th>
                  <th>Decision</th>
                  <th>Content Length</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {interventions.map((intervention, index) => (
                  <tr key={index}>
                    <td style={{ fontFamily: 'monospace', fontSize: '13px' }}>
                      {intervention.request.function_name}
                    </td>
                    <td>
                      {intervention.decision === 'return_value' ? (
                        <span className="badge badge-error">Intervened</span>
                      ) : intervention.decision === 'allow_original' ? (
                        <span className="badge badge-success">Allowed</span>
                      ) : (
                        <span className="badge badge-warning">Unknown</span>
                      )}
                    </td>
                    <td>{intervention.content_length} bytes</td>
                    <td style={{ color: 'var(--muted)', fontSize: '12px' }}>
                      {new Date(intervention.timestamp).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="insights">
        <h3>System Insights</h3>
        <pre>
{`System Status:
• Observability Server: ${status?.ok ? 'Online' : 'Offline'} (Port 5051)
• Database: ${status?.database.connected ? 'Connected' : 'Disconnected'}
• Storage: ${status?.data_source}
• Total Events: ${totalTraces}

Recent Activity:
• Active Traces: ${traces.length}
• Error Rate: ${traces.length > 0 ? Math.round(errorTraces / traces.length * 100) : 0}%
• Interventions: ${interventions.length} recent

Data Collection:
• Real-time trace ingestion active
• Event storage: ${status?.database.connected ? 'Persistent (Supabase)' : 'In-memory (temporary)'}
• Auto-refresh: 10 second intervals

Performance Monitoring:
• Span analysis: Available
• Error tracking: Active
• Duration monitoring: Enabled`}
        </pre>
      </div>
    </>
  );
}
