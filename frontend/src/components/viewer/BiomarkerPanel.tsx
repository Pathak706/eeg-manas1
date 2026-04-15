import type { BiomarkerSummary } from '../../types'

interface Props {
  biomarkers: BiomarkerSummary
}

function Bar({ label, value, maxVal = 1, color, suffix = '' }: {
  label: string; value: number; maxVal?: number; color: string; suffix?: string
}) {
  const pct = Math.min((value / maxVal) * 100, 100)
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-gray-500 w-12 text-right shrink-0">{label}</span>
      <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-700 w-14 text-right">
        {(value * 100).toFixed(0)}{suffix || '%'}
      </span>
    </div>
  )
}

function FaaIndicator({ faa }: { faa: number }) {
  const isNegative = faa < -0.1
  const isNeutral = faa >= -0.1 && faa <= 0.1
  const color = isNegative ? 'text-red-600' : isNeutral ? 'text-emerald-600' : 'text-blue-600'
  const bg = isNegative ? 'bg-red-50 border-red-200' : isNeutral ? 'bg-emerald-50 border-emerald-200' : 'bg-blue-50 border-blue-200'
  const label = isNegative
    ? 'Depression indicator (left frontal suppression)'
    : isNeutral
    ? 'Normal range'
    : 'Right-dominant (atypical)'

  return (
    <div className={`border rounded-lg p-3 ${bg}`}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold text-gray-600">Frontal Alpha Asymmetry (FAA)</div>
          <div className="text-xs text-gray-400 mt-0.5">{label}</div>
        </div>
        <div className={`text-2xl font-bold ${color}`}>{faa.toFixed(3)}</div>
      </div>
    </div>
  )
}

export default function BiomarkerPanel({ biomarkers }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100">
        <h3 className="font-semibold text-navy-600 text-sm">Brain Biomarkers</h3>
        <p className="text-xs text-gray-400 mt-0.5">EEG-derived biomarkers for depression assessment</p>
      </div>
      <div className="p-4 space-y-3">
        <FaaIndicator faa={biomarkers.frontal_alpha_asymmetry} />

        <div className="grid grid-cols-2 gap-4 mt-3">
          <div className="border border-gray-100 rounded-lg p-3">
            <div className="text-xs font-semibold text-gray-500 mb-0.5">Alpha/Beta Ratio</div>
            <div className="text-xl font-bold text-navy-600">{biomarkers.alpha_beta_ratio.toFixed(2)}</div>
          </div>
          <div className="border border-gray-100 rounded-lg p-3">
            <div className="text-xs font-semibold text-gray-500 mb-0.5">Theta/Beta Ratio</div>
            <div className="text-xl font-bold text-navy-600">{biomarkers.theta_beta_ratio.toFixed(2)}</div>
            {biomarkers.theta_beta_ratio > 2 && (
              <div className="text-xs text-amber-600 mt-0.5">Elevated (hypoarousal)</div>
            )}
          </div>
        </div>

        <div className="space-y-2 mt-2">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Band Power Distribution</div>
          <Bar label="Delta" value={biomarkers.delta_power} color="bg-purple-400" />
          <Bar label="Theta" value={biomarkers.theta_power} color="bg-blue-400" />
          <Bar label="Alpha" value={biomarkers.alpha_power} color="bg-emerald-400" />
          <Bar label="Beta" value={biomarkers.beta_power} color="bg-amber-400" />
          <Bar label="Gamma" value={biomarkers.gamma_power} color="bg-red-400" />
        </div>
      </div>
    </div>
  )
}
