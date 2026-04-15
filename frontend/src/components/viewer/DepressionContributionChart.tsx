import { useMemo } from 'react'
import Plot from 'react-plotly.js'
import type Plotly from 'plotly.js'
import type { EpochResult } from '../../types'

interface Props {
  epochs: EpochResult[]
  onEpochClick?: (epoch: EpochResult) => void
}

export default function DepressionContributionChart({ epochs, onEpochClick }: Props) {
  const colors = epochs.map((e) =>
    e.depression_contribution >= 0.7
      ? 'rgba(220, 38, 38, 0.85)'
      : e.depression_contribution >= 0.4
      ? 'rgba(217, 119, 6, 0.85)'
      : e.depression_contribution >= 0.2
      ? 'rgba(37, 99, 235, 0.7)'
      : 'rgba(5, 150, 105, 0.7)'
  )

  const data = useMemo(() => [
    {
      x: epochs.map((e) => e.start_time_sec),
      y: epochs.map((e) => e.depression_contribution),
      type: 'bar' as const,
      marker: { color: colors },
      hovertemplate:
        '<b>t=%{x:.1f}s</b><br>Depression contribution: %{y:.0%}<extra></extra>',
      name: 'Depression contribution',
    },
  ], [epochs, colors])

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100">
        <h3 className="font-semibold text-navy-600 text-sm">Depression Contribution by Epoch</h3>
        <p className="text-xs text-gray-400 mt-0.5">Each bar shows how much each epoch contributes to the overall depression score</p>
      </div>
      <Plot
        data={data}
        layout={{
          height: 200,
          margin: { t: 8, b: 40, l: 50, r: 8 },
          showlegend: false,
          paper_bgcolor: 'white',
          plot_bgcolor: '#f8fafc',
          xaxis: { title: 'Time (s)', tickfont: { size: 10 }, gridcolor: '#e2e8f0' },
          yaxis: {
            title: 'Contribution',
            range: [0, 1],
            tickformat: '.0%',
            tickfont: { size: 10 },
            gridcolor: '#e2e8f0',
          },
          shapes: [
            {
              type: 'line',
              x0: 0, x1: 1, xref: 'paper',
              y0: 0.5, y1: 0.5,
              line: { color: 'rgba(220, 38, 38, 0.4)', width: 1.5, dash: 'dash' },
            },
          ],
          annotations: [
            {
              x: 1, y: 0.5, xref: 'paper', yref: 'y',
              text: 'clinical threshold',
              showarrow: false,
              font: { size: 9, color: '#dc2626' },
              xanchor: 'right',
            },
          ],
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: '100%' }}
        onClick={(event: Plotly.PlotMouseEvent) => {
          if (onEpochClick && event.points[0]) {
            const idx = event.points[0].pointIndex
            if (epochs[idx]) onEpochClick(epochs[idx])
          }
        }}
      />
      <div className="px-4 pb-3 flex gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-500 rounded inline-block" /> Severe (&gt;70%)</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-amber-500 rounded inline-block" /> Moderate (40-70%)</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-600 rounded inline-block" /> Mild (20-40%)</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-emerald-600 rounded inline-block" /> Minimal (&lt;20%)</span>
      </div>
    </div>
  )
}
