import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import Plot from 'react-plotly.js'
import { studiesApi } from '../../api/studies'
import type { EpochResult, DisplayEEGData } from '../../types'

const WINDOW_SEC = 10

interface Props {
  studyId: number
  durationSec: number
  epochs: EpochResult[]
  onEpochClick?: (epoch: EpochResult) => void
}

export default function EEGWaveformViewer({ studyId, durationSec, epochs, onEpochClick }: Props) {
  const [windowStart, setWindowStart] = useState(0)
  const windowEnd = Math.min(windowStart + WINDOW_SEC, durationSec)

  const { data, isFetching } = useQuery({
    queryKey: ['display-data', studyId, windowStart],
    queryFn: () => studiesApi.getDisplayData(studyId, windowStart, windowEnd),
    placeholderData: (prev: DisplayEEGData | undefined) => prev,
  })

  // Seizure regions for shape overlays
  const seizureShapes = useMemo(() => {
    if (!epochs) return []
    return epochs
      .filter((e) => e.seizure_probability > 0.55)
      .map((e) => ({
        type: 'rect' as const,
        x0: e.start_time_sec,
        x1: e.end_time_sec,
        yref: 'paper' as const,
        y0: 0,
        y1: 1,
        fillcolor: 'rgba(220, 38, 38, 0.08)',
        line: { width: 0 },
      }))
  }, [epochs])

  const plotData = useMemo(() => {
    if (!data) return []
    const OFFSET = 150  // μV separation between channels
    return data.channels.map((ch, i) => {
      const raw = data.data[ch] || []
      const offset = (data.channels.length - 1 - i) * OFFSET
      return {
        x: data.times,
        y: raw.map((v) => v + offset),
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: ch,
        line: { width: 0.8, color: '#1e3a6e' },
        hovertemplate: `${ch}: %{customdata:.1f} μV<extra></extra>`,
        customdata: raw,
      }
    })
  }, [data])

  const yTickVals = useMemo(() => {
    if (!data) return []
    const OFFSET = 150
    return data.channels.map((_, i) => (data.channels.length - 1 - i) * OFFSET)
  }, [data])

  const yTickText = useMemo(() => data?.channels || [], [data])

  const canBack = windowStart > 0
  const canForward = windowEnd < durationSec

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <h3 className="font-semibold text-navy-600 text-sm">EEG Waveform</h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{windowStart.toFixed(0)}s – {windowEnd.toFixed(0)}s of {durationSec.toFixed(0)}s</span>
          <button
            onClick={() => setWindowStart(Math.max(0, windowStart - WINDOW_SEC))}
            disabled={!canBack || isFetching}
            className="text-xs px-3 py-1 border rounded-lg disabled:opacity-40 hover:bg-gray-50"
          >
            ◀ Prev
          </button>
          <button
            onClick={() => setWindowStart(Math.min(durationSec - WINDOW_SEC, windowStart + WINDOW_SEC))}
            disabled={!canForward || isFetching}
            className="text-xs px-3 py-1 border rounded-lg disabled:opacity-40 hover:bg-gray-50"
          >
            Next ▶
          </button>
        </div>
      </div>

      {/* Time scrubber */}
      <div className="px-4 py-2 border-b border-gray-50">
        <input
          type="range"
          min={0}
          max={Math.max(0, durationSec - WINDOW_SEC)}
          step={1}
          value={windowStart}
          onChange={(e) => setWindowStart(Number(e.target.value))}
          className="w-full accent-navy-600"
        />
        <div className="flex justify-between text-xs text-gray-300">
          <span>0s</span><span>{durationSec.toFixed(0)}s</span>
        </div>
      </div>

      {isFetching && !data && (
        <div className="h-64 flex items-center justify-center text-gray-400 text-sm animate-pulse">
          Loading waveform…
        </div>
      )}

      {plotData.length > 0 && (
        <div style={{ opacity: isFetching ? 0.6 : 1, transition: 'opacity 0.2s' }}>
          <Plot
            data={plotData}
            layout={{
              height: 480,
              margin: { t: 8, b: 32, l: 50, r: 8 },
              showlegend: false,
              paper_bgcolor: 'white',
              plot_bgcolor: '#f8fafc',
              xaxis: {
                title: 'Time (s)',
                tickfont: { size: 10 },
                range: [windowStart, windowEnd],
                gridcolor: '#e2e8f0',
              },
              yaxis: {
                tickvals: yTickVals,
                ticktext: yTickText,
                tickfont: { size: 9 },
                showgrid: false,
                zeroline: false,
              },
              shapes: seizureShapes,
            }}
            config={{ responsive: true, displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </div>
      )}

      <div className="px-4 pb-2 flex items-center gap-3 text-xs text-gray-400">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 bg-red-100 border border-red-200 rounded-sm" />
          Seizure probability &gt; 55%
        </span>
        <span>· Amplitude offset: 150 μV per channel</span>
      </div>
    </div>
  )
}
