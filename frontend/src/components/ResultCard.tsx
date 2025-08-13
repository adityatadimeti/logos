import React from 'react'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend } from 'chart.js'
import { Bar, Line, Pie } from 'react-chartjs-2'
ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend)

type Props = {
  payload: any
}

export default function ResultCard({ payload }: Props) {
  const chartPayload = payload && payload.chartjs
  const hasImage = payload && payload.image_base64
  const answer = payload && payload.answer
  const alt = (payload && payload.alt) || 'Visualization'

  const renderChart = () => {
    if (!chartPayload) return null
    const type = (chartPayload.type || 'bar').toLowerCase()
    const data = chartPayload.data || { labels: [], datasets: [] }
    const options = chartPayload.options || {}
    
    if (type === 'line') {
      return <Line data={data} options={options} />
    }
    return <Bar data={data} options={options} />
  }

  return (
    <section className="card">
      <h3>Result</h3>

      {answer && typeof answer === 'string' && answer.trim() && (
        <div style={{ 
          margin: '0 0 20px', 
          padding: '16px', 
          background: 'rgba(79, 70, 229, 0.05)', 
          border: '1px solid rgba(79, 70, 229, 0.1)', 
          borderRadius: '8px',
          fontSize: '16px',
          lineHeight: '1.6'
        }}>
          {answer}
        </div>
      )}

      {chartPayload && (
        <div className="img-wrap">
          {renderChart()}
        </div>
      )}

      {hasImage && !chartPayload && (
        <div className="img-wrap">
          <img src={`data:image/png;base64,${payload.image_base64}`} alt={alt} />
        </div>
      )}

      <details className="details" style={{ marginTop: '20px' }}>
        <summary style={{ cursor: 'pointer', color: 'var(--muted)', fontSize: '14px' }}>
          View raw data
        </summary>
        <pre style={{ 
          marginTop: '12px', 
          fontSize: '12px', 
          background: 'rgba(0,0,0,0.2)', 
          padding: '12px', 
          borderRadius: '6px',
          maxHeight: '300px',
          overflow: 'auto'
        }}>
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    </section>
  )
} 