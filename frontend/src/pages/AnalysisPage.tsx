import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { studiesApi } from '../api/studies'
import { analysisApi } from '../api/analysis'
import EEGWaveformViewer from '../components/viewer/EEGWaveformViewer'
import DepressionContributionChart from '../components/viewer/DepressionContributionChart'
import ChannelAttentionHeatmap from '../components/viewer/ChannelAttentionHeatmap'
import BiomarkerPanel from '../components/viewer/BiomarkerPanel'
import type { EpochResult } from '../types'

const RISK_STYLES: Record<string, { color: string; bg: string }> = {
  Minimal:             { color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200' },
  Mild:                { color: 'text-blue-600',    bg: 'bg-blue-50 border-blue-200' },
  Moderate:            { color: 'text-amber-600',   bg: 'bg-amber-50 border-amber-200' },
  'Moderately Severe': { color: 'text-orange-600',  bg: 'bg-orange-50 border-orange-200' },
  Severe:              { color: 'text-red-600',     bg: 'bg-red-50 border-red-200' },
}

function ConfidenceBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    HIGH: 'bg-emerald-100 text-emerald-700 border-emerald-300',
    MEDIUM: 'bg-amber-100 text-amber-700 border-amber-300',
    LOW: 'bg-red-100 text-red-700 border-red-300',
    UNKNOWN: 'bg-gray-100 text-gray-500 border-gray-300',
  }
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${colors[level] ?? colors.UNKNOWN}`}>
      {level} confidence
    </span>
  )
}

export default function AnalysisPage() {
  const { studyId } = useParams<{ studyId: string }>()
  const navigate = useNavigate()
  const sid = Number(studyId)
  const [selectedEpoch, setSelectedEpoch] = useState<EpochResult | undefined>()

  const { data: study } = useQuery({ queryKey: ['study', sid], queryFn: () => studiesApi.get(sid) })
  const { data: analysis, isLoading } = useQuery({
    queryKey: ['analysis', sid],
    queryFn: () => analysisApi.get(sid),
  })

  const isPdf = study?.source_type === 'pdf'

  const { data: extractedText } = useQuery({
    queryKey: ['extracted-text', sid],
    queryFn: () => studiesApi.getExtractedText(sid),
    enabled: isPdf && !!analysis,
  })

  const [showExtractedText, setShowExtractedText] = useState(false)

  const riskStyle = analysis ? (RISK_STYLES[analysis.depression_risk_level] ?? RISK_STYLES.Minimal) : { color: '', bg: '' }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => navigate('/')} className="text-navy-600 text-sm font-medium hover:underline">
          ← Patients
        </button>
        <span className="text-gray-300">›</span>
        <span className="text-sm text-gray-500 flex items-center gap-2">
          Study #{sid}
          {study?.is_synthetic && <span className="text-purple-600 font-medium">(Demo)</span>}
          {isPdf && (
            <span className="inline-flex items-center gap-1 bg-rose-100 text-rose-700 text-xs font-semibold px-2 py-0.5 rounded-full border border-rose-300">
              PDF Source
            </span>
          )}
        </span>
      </div>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-navy-600">EEG Depression Assessment</h1>
          <p className="text-sm text-gray-500 mt-1">
            {study
              ? isPdf
                ? `${study.recording_duration_sec.toFixed(0)}s estimated · NLP-derived · ${study.original_filename || 'PDF report'}`
                : `${study.recording_duration_sec.toFixed(0)}s · ${study.channel_count} channels · ${study.sample_rate_hz} Hz`
              : ''}
          </p>
        </div>
        <button
          onClick={() => navigate(`/report/${sid}`)}
          className="bg-navy-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-navy-700 transition-colors"
        >
          Clinical Report
        </button>
      </div>

      {isLoading && (
        <div className="text-center py-16 text-gray-400 animate-pulse">Loading analysis...</div>
      )}

      {analysis && (
        <>
          {/* Summary banner */}
          <div className={`border rounded-xl p-5 mb-6 ${riskStyle.bg}`}>
            <div className="flex items-start gap-6">
              <div className="text-center">
                <div className={`text-4xl font-black ${riskStyle.color}`}>
                  {analysis.depression_severity_score.toFixed(1)}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">/ 27 PHQ-9</div>
                <div className={`text-xs font-bold mt-1 ${riskStyle.color}`}>
                  {analysis.depression_risk_level.toUpperCase()}
                </div>
              </div>
              <div className="flex-1">
                <div className="text-xs font-semibold text-gray-600 mb-1 uppercase tracking-wide">Background Rhythm</div>
                <div className="text-sm text-gray-700 mb-2">{analysis.background_rhythm}</div>
                <div className="text-xs font-semibold text-gray-600 mb-1 uppercase tracking-wide">Frontal Alpha Asymmetry</div>
                <div className="text-sm text-gray-700 mb-2">
                  FAA = {analysis.frontal_alpha_asymmetry.toFixed(3)}
                  {analysis.frontal_alpha_asymmetry < -0.1 && (
                    <span className="ml-2 text-red-600 text-xs font-semibold">(depression indicator)</span>
                  )}
                </div>
                <div className="text-xs text-gray-500">{analysis.model_version} · {analysis.processing_time_ms}ms</div>
              </div>
              {analysis.clinical_flags.length > 0 && (
                <div className="shrink-0">
                  <div className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">Clinical Flags</div>
                  <div className="flex flex-col gap-1.5">
                    {analysis.clinical_flags.slice(0, 4).map((f, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <span className={`text-xs font-bold ${f.severity === 'HIGH' ? 'text-red-600' : f.severity === 'MEDIUM' ? 'text-amber-600' : 'text-emerald-600'}`}>
                          {f.severity}
                        </span>
                        <span className="text-xs text-gray-600">{f.flag_type.replace(/_/g, ' ')}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Biomarker Panel + Depression Chart side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <BiomarkerPanel biomarkers={analysis.biomarkers} />
            <DepressionContributionChart epochs={analysis.epochs} onEpochClick={setSelectedEpoch} />
          </div>

          {/* Visualizations */}
          <div className="space-y-4">
            {isPdf ? (
              <div className="bg-gray-50 border border-gray-200 rounded-xl p-6 text-center text-sm text-gray-500">
                <p className="font-medium text-gray-600">Waveform data not available for PDF-sourced studies.</p>
                <p className="text-xs mt-1 text-gray-400">Upload an EDF file to see the EEG waveform.</p>
              </div>
            ) : (
              <EEGWaveformViewer
                studyId={sid}
                durationSec={study?.recording_duration_sec || 120}
                epochs={analysis.epochs}
                onEpochClick={setSelectedEpoch}
              />
            )}

            <ChannelAttentionHeatmap epochs={analysis.epochs} selectedEpochIndex={selectedEpoch?.epoch_index} />
          </div>

          {/* Extracted report text (PDF only) */}
          {isPdf && (
            <div className="mt-4 bg-rose-50 border border-rose-200 rounded-xl overflow-hidden">
              <button
                onClick={() => setShowExtractedText((v) => !v)}
                className="w-full flex items-center justify-between px-5 py-3 text-left"
              >
                <span className="font-semibold text-rose-800 text-sm flex items-center gap-2">
                  Extracted Report Text
                  {extractedText && <ConfidenceBadge level={extractedText.source_confidence} />}
                </span>
                <span className="text-rose-500 text-xs">{showExtractedText ? 'collapse' : 'expand'}</span>
              </button>
              {showExtractedText && (
                <div className="px-5 pb-5">
                  <pre className="text-xs text-gray-700 whitespace-pre-wrap bg-white border border-rose-100 rounded-lg p-4 max-h-96 overflow-y-auto font-mono leading-relaxed">
                    {extractedText?.markdown_text || 'Loading...'}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Clinical impression */}
          <div className="mt-4 bg-blue-50 border border-blue-100 rounded-xl p-5">
            <h3 className="font-semibold text-navy-600 text-sm mb-2">Clinical Impression (AI-generated)</h3>
            <p className="text-sm text-slate-700 leading-relaxed">{analysis.clinical_impression}</p>
          </div>

          {/* Epoch table */}
          <div className="mt-4 bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100">
              <h3 className="font-semibold text-navy-600 text-sm">Top Epochs by Depression Contribution</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-navy-600 text-white">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold uppercase tracking-wide">Epoch</th>
                    <th className="px-3 py-2 text-left font-semibold uppercase tracking-wide">Time</th>
                    <th className="px-3 py-2 text-left font-semibold uppercase tracking-wide">Depression Contrib.</th>
                    <th className="px-3 py-2 text-left font-semibold uppercase tracking-wide">FAA</th>
                    <th className="px-3 py-2 text-left font-semibold uppercase tracking-wide">Dom. Freq.</th>
                    <th className="px-3 py-2 text-left font-semibold uppercase tracking-wide">Top Channels</th>
                    <th className="px-3 py-2 text-left font-semibold uppercase tracking-wide">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {[...analysis.epochs]
                    .sort((a, b) => b.depression_contribution - a.depression_contribution)
                    .slice(0, 10)
                    .map((ep) => {
                      const topChs = Object.entries(ep.channel_attention)
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 3)
                        .map(([ch]) => ch)
                        .join(', ')
                      const pct = (ep.depression_contribution * 100).toFixed(0) + '%'
                      const color =
                        ep.depression_contribution >= 0.7 ? 'text-red-600 font-bold'
                        : ep.depression_contribution >= 0.4 ? 'text-amber-600 font-semibold'
                        : 'text-emerald-600'
                      return (
                        <tr
                          key={ep.epoch_index}
                          className="hover:bg-blue-50 cursor-pointer transition-colors"
                          onClick={() => setSelectedEpoch(ep)}
                        >
                          <td className="px-3 py-2">{ep.epoch_index + 1}</td>
                          <td className="px-3 py-2">{ep.start_time_sec.toFixed(1)}s - {ep.end_time_sec.toFixed(1)}s</td>
                          <td className={`px-3 py-2 ${color}`}>{pct}</td>
                          <td className="px-3 py-2">{ep.frontal_alpha_asymmetry.toFixed(3)}</td>
                          <td className="px-3 py-2">{ep.dominant_frequency_hz.toFixed(1)} Hz</td>
                          <td className="px-3 py-2 text-gray-600">{topChs}</td>
                          <td className="px-3 py-2 text-gray-500">{(ep.confidence * 100).toFixed(0)}%</td>
                        </tr>
                      )
                    })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Disclaimer */}
          <div className="mt-4 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
            <strong>AI Depression Screening Only.</strong> EEG biomarkers are complementary to clinical assessment.
            All findings require review by a qualified psychiatrist alongside standardised instruments (PHQ-9, BDI-II).
          </div>
        </>
      )}
    </div>
  )
}
