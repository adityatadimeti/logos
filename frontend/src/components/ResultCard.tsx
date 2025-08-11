import React from 'react'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend } from 'chart.js'
import { Bar, Line } from 'react-chartjs-2'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend)

type Props = {
  payload: any
}

export default function ResultCard({ payload }: Props) {
  const chartPayload = payload && payload.chartjs
  const hasImage = payload && payload.image_base64
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

      <details className="details">
        <summary>Raw result JSON</summary>
        <pre>{JSON.stringify(payload, null, 2)}</pre>
      </details>
    </section>
  )
} 