import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiClient } from '../api';
import { TraceEvent } from '../types';

export default function TraceView() {
  const { traceId } = useParams<{ traceId: string }>();
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedPreviews, setExpandedPreviews] = useState<Set<number>>(new Set());
  const [diagnosing, setDiagnosing] = useState(false);
  const [diagnosis, setDiagnosis] = useState<string | null>(null);
  const [diagnosisError, setDiagnosisError] = useState<string | null>(null);
  const [showDiagnosisModal, setShowDiagnosisModal] = useState(false);

  useEffect(() => {
    const fetchTraceDetails = async () => {
      if (!traceId) return;
      
      try {
        setLoading(true);
        const traceData = await apiClient.getTraceDetails(traceId);
        setEvents(traceData);
        setError(null);
      } catch (err) {
        setError('Failed to fetch trace details');
        console.error('Error fetching trace details:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchTraceDetails();
  }, [traceId]);

  if (!traceId) {
    return (
      <div className="empty-state">
        <h3>Invalid Trace ID</h3>
        <p>Please provide a valid trace ID.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        Loading trace details...
      </div>
    );
  }

  const getPreview = (event: TraceEvent) => {
    if (event.event_type === 'span_start') {
      const parts = [];
      if (event.args_preview) parts.push(`args=${event.args_preview}`);
      if (event.kwargs_preview) parts.push(`kwargs=${event.kwargs_preview}`);
      return parts.join('  ');
    } else if (event.event_type === 'span_end') {
      if (event.status === 'error') {
        return `${event.error_type}: ${event.error_message}`;
      } else {
        return event.result_preview || '';
      }
    }
    return '';
  };

  const togglePreviewExpansion = (index: number) => {
    const newExpanded = new Set(expandedPreviews);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedPreviews(newExpanded);
  };

  const handleDiagnose = async () => {
    if (!traceId) return;
    
    setDiagnosing(true);
    setDiagnosis(null);
    setDiagnosisError(null);
    
    try {
      // Prepare the diagnosis request payload
      const feedbackData = {
        sentiment: "Dislike",
        categories: "Being Lazy",
        comments: "I asked for a pie chart to capture my spending, but instead was given a bar graph split between vendors. Wish i couldve gotten a pie chart since that's what I asked for!"
      };
      
      const payload = {
        traceId,
        events,
        feedback: feedbackData
      };

      const response = await fetch('http://127.0.0.1:5051/diagnose', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      console.log('Diagnosis response:', result);
      
      if (result.error) {
        throw new Error(result.error);
      }
      
      const diagnosisText = result.diagnosis || 'No diagnosis available';
      console.log('Setting diagnosis:', diagnosisText);
      console.log('Diagnosis text length:', diagnosisText.length);
      setDiagnosis(diagnosisText);
      setShowDiagnosisModal(true);
      console.log('Diagnosis state should be set now');
    } catch (err) {
      console.error('Error during diagnosis:', err);
      setDiagnosisError(err instanceof Error ? err.message : 'Failed to diagnose issue');
      setShowDiagnosisModal(true);
    } finally {
      setDiagnosing(false);
    }
  };

  const formatDiagnosisText = (text: string) => {
    // Split text into parts, detecting code blocks
    const parts = text.split(/```(\w+)?\n([\s\S]*?)```/);
    const elements = [];
    
    for (let i = 0; i < parts.length; i++) {
      if (i % 3 === 0) {
        // Regular text
        if (parts[i].trim()) {
          elements.push(
            <span key={i} style={{ lineHeight: '1.6' }}>
              {parts[i]}
            </span>
          );
        }
      } else if (i % 3 === 2) {
        // Code block
        const language = parts[i - 1] || 'javascript';
        const code = parts[i];
        elements.push(
          <div
            key={i}
            style={{
              margin: '12px 0',
              padding: '16px',
              background: '#1a1a1a',
              border: '1px solid #333',
              borderRadius: '8px',
              fontFamily: 'Monaco, Menlo, "SF Mono", Consolas, "Liberation Mono", monospace',
              fontSize: '13px',
              lineHeight: '1.4',
              color: '#f8f8f2',
              whiteSpace: 'pre',
              overflow: 'auto'
            }}
          >
            <div style={{ 
              marginBottom: '8px', 
              fontSize: '11px', 
              color: '#888',
              textTransform: 'uppercase',
              fontWeight: '600'
            }}>
              {language}
            </div>
            {code}
          </div>
        );
      }
    }
    
    return elements;
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
              Trace Analysis
            </h1>
            <p style={{ 
              margin: '4px 0 0 0', 
              fontSize: '16px', 
              color: 'var(--muted)',
              fontWeight: '400'
            }}>
              {events.length} events • Trace ID: {traceId}
            </p>
          </div>
        </div>
      </header>

      {error && (
        <div className="card">
          <div className="card-body">
            <div className="empty-state">
              <h3>Error</h3>
              <p>{error}</p>
              <p style={{ marginTop: '16px', fontSize: '14px', color: 'var(--muted)' }}>
                You can view this trace on the{' '}
                <a 
                  href={`http://127.0.0.1:5051/trace/${traceId}`} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  style={{ color: 'var(--accent)' }}
                >
                  full observability dashboard
                </a>
              </p>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-start', width: '100%' }}>
        <div className="card" style={{ flex: '4', minWidth: '1000px' }}>
          <div className="card-header">
            <h2>Trace Events</h2>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button onClick={() => window.location.reload()} className="btn btn-secondary">
                Refresh
              </button>
              <Link to="/" className="btn">
                Back to Dashboard
              </Link>
            </div>
          </div>
        
        {events.length === 0 ? (
          <div className="card-body">
            <div className="empty-state">
              <h3>No events found</h3>
              <p>This trace doesn't contain any events yet.</p>
              <p style={{ marginTop: '16px', fontSize: '14px', color: 'var(--muted)' }}>
                Try viewing this trace on the{' '}
                <a 
                  href={`http://127.0.0.1:5051/trace/${traceId}`} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  style={{ color: 'var(--accent)' }}
                >
                  full observability dashboard
                </a>
              </p>
            </div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Event Type</th>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Duration</th>
                  <th>Preview</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event, index) => (
                  <tr key={index}>
                    <td style={{ 
                      color: 'var(--muted)', 
                      fontFamily: 'monospace', 
                      fontSize: '12px', 
                      width: '140px' 
                    }}>
                      {event.timestamp ? event.timestamp.slice(-12, -4) : ''}
                    </td>
                    <td style={{ fontWeight: 500, fontSize: '13px' }}>
                      {event.event_type || ''}
                    </td>
                                         <td style={{ 
                       fontFamily: 'monospace', 
                       fontSize: '13px', 
                       minWidth: '250px',
                       maxWidth: '300px', 
                       wordBreak: 'break-word' 
                     }}>
                      {event.name || ''}
                    </td>
                    <td>
                      {event.status === 'error' ? (
                        <span className="badge badge-error">Error</span>
                      ) : event.status === 'ok' ? (
                        <span className="badge badge-success">OK</span>
                      ) : null}
                    </td>
                    <td>
                      {event.duration_ms ? `${event.duration_ms}ms` : ''}
                    </td>
                    <td>
                      {getPreview(event) && (
                        <div style={{ position: 'relative' }}>
                          <div 
                            style={{
                              background: 'rgba(15, 16, 32, 0.5)',
                              border: '1px solid var(--border)',
                              borderRadius: '6px',
                              padding: '12px',
                              fontFamily: 'monospace',
                              fontSize: '12px',
                              lineHeight: 1.4,
                              color: 'var(--muted)',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              width: '100%',
                              maxHeight: expandedPreviews.has(index) ? 'none' : '100px',
                              overflowY: expandedPreviews.has(index) ? 'visible' : 'auto',
                              transition: 'max-height 0.2s ease-in-out'
                            }}
                          >
                            {getPreview(event)}
                          </div>
                          <button
                            onClick={() => togglePreviewExpansion(index)}
                            style={{
                              position: 'absolute',
                              top: '4px',
                              right: '4px',
                              background: 'rgba(0, 0, 0, 0.7)',
                              border: '1px solid var(--border)',
                              borderRadius: '4px',
                              color: 'var(--text)',
                              cursor: 'pointer',
                              padding: '2px 4px',
                              fontSize: '10px',
                              lineHeight: 1,
                              opacity: 0.7,
                              transition: 'opacity 0.2s ease'
                            }}
                            onMouseEnter={(e) => (e.target as HTMLButtonElement).style.opacity = '1'}
                            onMouseLeave={(e) => (e.target as HTMLButtonElement).style.opacity = '0.7'}
                            title={expandedPreviews.has(index) ? 'Collapse' : 'Expand'}
                          >
                            {expandedPreviews.has(index) ? '↗' : '↙'}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        </div>

        <div className="card" style={{ flex: '2', minWidth: '400px', maxWidth: '500px' }}>
          <div className="card-header">
            <h2>{traceId?.startsWith('10b29b05') ? 'Feedback from Slack' : 'No User Feedback'}</h2>
          </div>
          <div className="card-body">
            {traceId?.startsWith('10b29b05') ? (
              <>
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontWeight: '500', marginBottom: '4px', fontSize: '14px' }}>Sentiment:</div>
                  <span className="badge badge-error" style={{ fontSize: '12px' }}>Dislike</span>
                </div>
                
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontWeight: '500', marginBottom: '4px', fontSize: '14px' }}>Categories:</div>
                  <span className="badge" style={{ 
                    backgroundColor: 'rgba(79, 70, 229, 0.1)', 
                    color: 'var(--accent)', 
                    border: '1px solid rgba(79, 70, 229, 0.2)',
                    fontSize: '12px'
                  }}>Being Lazy</span>
                </div>
                
                <div>
                  <div style={{ fontWeight: '500', marginBottom: '8px', fontSize: '14px' }}>Comments:</div>
                  <div style={{ 
                    fontSize: '14px', 
                    lineHeight: '1.5', 
                    color: 'var(--text)', 
                    background: 'rgba(15, 16, 32, 0.3)',
                    border: '1px solid var(--border)',
                    borderRadius: '6px',
                    padding: '12px'
                  }}>
                    I asked for a pie chart to capture my spending, but instead was given a bar graph split between vendors. Wish i couldve gotten a pie chart since that's what I asked for!
                  </div>
                </div>
              </>
            ) : (
              <div style={{ 
                fontSize: '14px', 
                lineHeight: '1.5', 
                color: 'var(--muted)', 
                textAlign: 'center',
                padding: '20px 0'
              }}>
                No user feedback available for this trace.
              </div>
            )}
            
            <div style={{ marginTop: '20px', textAlign: 'center' }}>
              <button
                onClick={handleDiagnose}
                disabled={diagnosing}
                className="btn"
                style={{
                  backgroundColor: diagnosing ? 'var(--muted)' : 'var(--accent)',
                  color: 'white',
                  cursor: diagnosing ? 'not-allowed' : 'pointer',
                  opacity: diagnosing ? 0.6 : 1
                }}
              >
                {diagnosing 
                  ? 'Analyzing...' 
                  : traceId?.startsWith('10b29b05') 
                    ? 'Diagnose Issue' 
                    : 'Analyze Trace for Issues'
                }
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Diagnosis Modal */}
      {showDiagnosisModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div style={{
            backgroundColor: 'var(--bg)',
            borderRadius: '12px',
            border: '1px solid var(--border)',
            maxWidth: '800px',
            maxHeight: '80vh',
            width: '100%',
            overflow: 'hidden',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.4)'
          }}>
            <div style={{
              padding: '20px 24px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <h2 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>
                Diagnosis
              </h2>
              <button
                onClick={() => setShowDiagnosisModal(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '20px',
                  cursor: 'pointer',
                  color: 'var(--muted)',
                  padding: '4px'
                }}
              >
                ✕
              </button>
            </div>
            
            <div style={{
              padding: '24px',
              overflow: 'auto',
              maxHeight: 'calc(80vh - 80px)',
              fontSize: '14px',
              lineHeight: '1.6',
              color: 'var(--text)'
            }}>
              {diagnosisError ? (
                <div style={{
                  padding: '16px',
                  background: 'rgba(220, 38, 127, 0.1)',
                  border: '1px solid rgba(220, 38, 127, 0.2)',
                  borderRadius: '8px',
                  color: 'var(--error)'
                }}>
                  <strong>Error:</strong> {diagnosisError}
                </div>
              ) : diagnosis ? (
                <div>
                  {formatDiagnosisText(diagnosis)}
                </div>
              ) : (
                <div>No diagnosis available</div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
