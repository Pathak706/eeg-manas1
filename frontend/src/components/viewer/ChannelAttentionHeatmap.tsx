import { useMemo } from 'react'
import Plot from 'react-plotly.js'
import type { EpochResult } from '../../types'

interface Props {
  epochs: EpochResult[]
  selectedEpochIndex?: number
}

export default function ChannelAttentionHeatmap({ epochs, selectedEpochIndex }: Props) {
  const channels = useMemo(() => {
    if (!epochs.length) return []
    return Object.keys(epochs[0].channel_attention)
  }, [epochs])

  const zMatrix = useMemo(() => {
    // rows = channels, cols = epochs
    return channels.map((ch) => epochs.map((ep) => ep.channel_attention[ch] ?? 0))
  }, [channels, epochs])

  const xLabels = epochs.map((e) => `${e.start_time_sec.toFixed(0)}s`)

  const shapes = useMemo(() => {
    if (selectedEpochIndex === undefined) return []
    return [
      {
        type: 'line' as const,
        x0: selectedEpochIndex - 0.5,
        x1: selectedEpochIndex - 0.5,
        yref: 'paper' as const,
        y0: 0,
        y1: 1,
        line: { color: '#1a3a6e', width: 2 },
      },
      {
        type: 'line' as const,
        x0: selectedEpochIndex + 0.5,
        x1: selectedEpochIndex + 0.5,
        yref: 'paper' as const,
        y0: 0,
        y1: 1,
        line: { color: '#1a3a6e', width: 2 },
      },
    ]
  }, [selectedEpochIndex])

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100">
        <h3 className="font-semibold text-navy-600 text-sm">Channel Attention Heatmap</h3>
        <p className="text-xs text-gray-400 mt-0.5">MANAS-1 attention weight per channel per epoch</p>
      </div>
      {channels.length === 0 ? (
        <div className="h-40 flex items-center justify-center text-gray-400 text-sm">No data</div>
      ) : (
        <Plot
          data={[
            {
              z: zMatrix,
              x: xLabels,
              y: channels,
              type: 'heatmap',
              colorscale: 'YlOrRd',
              showscale: true,
              hovertemplate: 'Channel: %{y}<br>Epoch: %{x}<br>Attention: %{z:.3f}<extra></extra>',
              colorbar: { thickness: 12, len: 0.9, tickfont: { size: 9 } },
            },
          ]}
          layout={{
            height: 280,
            margin: { t: 8, b: 50, l: 45, r: 60 },
            paper_bgcolor: 'white',
            plot_bgcolor: 'white',
            xaxis: {
              title: 'Epoch (start time)',
              tickfont: { size: 9 },
              nticks: Math.min(20, epochs.length),
            },
            yaxis: { tickfont: { size: 9 }, autorange: 'reversed' },
            shapes,
          }}
          config={{ responsive: true, displayModeBar: false }}
          style={{ width: '100%' }}
        />
      )}
    </div>
  )
}
