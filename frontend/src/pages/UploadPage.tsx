import { useCallback, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import { patientsApi } from '../api/patients'
import { useStudyUpload, type UploadStep } from '../hooks/useStudyUpload'

const STEPS: { key: UploadStep; label: string }[] = [
  { key: 'uploading',     label: 'Uploading' },
  { key: 'preprocessing', label: 'Preprocessing' },
  { key: 'analyzing',     label: 'AI Analysis' },
  { key: 'complete',      label: 'Complete' },
]

function stepIndex(step: UploadStep) {
  return STEPS.findIndex((s) => s.key === step)
}

type Tab = 'edf' | 'pdf' | 'demo'

export default function UploadPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const navigate = useNavigate()
  const pid = Number(patientId)
  const [activeTab, setActiveTab] = useState<Tab>('edf')

  const { data: patient } = useQuery({ queryKey: ['patient', pid], queryFn: () => patientsApi.get(pid) })
  const { state, upload, uploadPdf, loadDemo, reset } = useStudyUpload(pid)
  const pdfInputRef = useRef<HTMLInputElement>(null)

  const onDrop = useCallback(
    (accepted: File[]) => { if (accepted[0]) upload(accepted[0]) },
    [upload]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/octet-stream': ['.edf'], 'application/edf': ['.edf'] },
    maxFiles: 1,
    disabled: state.step !== 'idle',
  })

  const currentStepIdx = stepIndex(state.step)

  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: 'edf',  label: 'EDF File',       icon: '📂' },
    { key: 'pdf',  label: 'Clinical PDF',   icon: '📄' },
    { key: 'demo', label: 'Demo / Synthetic', icon: '🧪' },
  ]

  return (
    <div className="max-w-2xl mx-auto p-6">
      <button onClick={() => navigate('/')} className="text-navy-600 text-sm font-medium hover:underline mb-4 block">
        ← Back to Patients
      </button>

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-navy-600">New EEG Study</h1>
        {patient && (
          <p className="text-sm text-gray-500 mt-1">
            Patient: <span className="font-semibold text-gray-700">{patient.name}</span> · MRN: {patient.mrn}
          </p>
        )}
      </div>

      {state.step === 'idle' && (
        <>
          {/* Tab switcher */}
          <div className="flex border border-gray-200 rounded-xl overflow-hidden mb-6 bg-gray-50">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-semibold transition-all ${
                  activeTab === t.key
                    ? 'bg-white text-navy-600 shadow-sm border-b-2 border-navy-600'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                <span>{t.icon}</span>
                <span>{t.label}</span>
              </button>
            ))}
          </div>

          {/* EDF upload tab */}
          {activeTab === 'edf' && (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all ${
                isDragActive ? 'border-navy-600 bg-blue-50' : 'border-gray-300 hover:border-navy-600 hover:bg-gray-50'
              }`}
            >
              <input {...getInputProps()} />
              <div className="text-5xl mb-4">📂</div>
              <p className="font-semibold text-gray-700 text-lg">Drop an EDF file here</p>
              <p className="text-sm text-gray-400 mt-2">or click to browse · EDF / EDF+ format</p>
              <p className="text-xs text-gray-300 mt-1">Min 2 channels · 128 Hz · 10 seconds</p>
            </div>
          )}

          {/* PDF upload tab */}
          {activeTab === 'pdf' && (
            <div className="bg-gradient-to-br from-rose-50 to-orange-50 border border-rose-200 rounded-xl p-8 text-center">
              <div className="text-5xl mb-4">📄</div>
              <h3 className="font-bold text-rose-800 text-lg mb-2">Upload Clinical EEG Report (PDF)</h3>
              <p className="text-sm text-rose-700 mb-6 max-w-sm mx-auto">
                Have an existing EEG interpretation letter or discharge summary?
                Our NLP pipeline extracts clinical findings and generates a structured
                MANAS-1 depression assessment report.
              </p>
              <input
                ref={pdfInputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) uploadPdf(f)
                  e.target.value = ''
                }}
              />
              <button
                onClick={() => pdfInputRef.current?.click()}
                className="bg-rose-600 text-white px-8 py-3 rounded-lg text-sm font-semibold hover:bg-rose-700 transition-colors"
              >
                Select PDF Report
              </button>
              <p className="text-xs text-rose-400 mt-3">
                Supports text-based PDFs (discharge summaries, EEG letters). No raw signal file needed.
              </p>
            </div>
          )}

          {/* Demo tab */}
          {activeTab === 'demo' && (
            <div className="bg-gradient-to-br from-indigo-50 to-blue-50 border border-indigo-200 rounded-xl p-8 text-center">
              <div className="text-5xl mb-4">🧪</div>
              <h3 className="font-bold text-indigo-800 text-lg mb-2">Generate Synthetic EEG</h3>
              <p className="text-sm text-indigo-600 mb-6 max-w-sm mx-auto">
                Generate a synthetic 19-channel 2-minute EEG recording with realistic biomarkers.
                Use the depressed variant to demonstrate frontal alpha asymmetry and MANAS-1 flagging.
              </p>
              <div className="flex gap-3 justify-center flex-wrap">
                <button
                  onClick={() => loadDemo(true)}
                  className="bg-indigo-600 text-white px-6 py-3 rounded-lg text-sm font-semibold hover:bg-indigo-700 transition-colors"
                >
                  Demo with Depression Pattern
                </button>
                <button
                  onClick={() => loadDemo(false)}
                  className="border border-indigo-300 text-indigo-700 px-6 py-3 rounded-lg text-sm font-semibold hover:bg-indigo-50 transition-colors"
                >
                  Demo — Normal EEG
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {state.step !== 'idle' && state.step !== 'error' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8">
          <h2 className="text-lg font-bold text-navy-600 mb-6">Processing EEG…</h2>

          <div className="flex items-center gap-0 mb-8">
            {STEPS.map((s, i) => (
              <div key={s.key} className="flex items-center flex-1">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all ${
                      i < currentStepIdx
                        ? 'bg-green-500 border-green-500 text-white'
                        : i === currentStepIdx
                        ? 'bg-navy-600 border-navy-600 text-white animate-pulse'
                        : 'bg-white border-gray-300 text-gray-400'
                    }`}
                  >
                    {i < currentStepIdx ? '✓' : i + 1}
                  </div>
                  <span className={`text-xs mt-1 font-medium ${i === currentStepIdx ? 'text-navy-600' : 'text-gray-400'}`}>
                    {s.label}
                  </span>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`flex-1 h-0.5 mb-5 ${i < currentStepIdx ? 'bg-green-500' : 'bg-gray-200'}`} />
                )}
              </div>
            ))}
          </div>

          {state.step === 'uploading' && (
            <div>
              <div className="flex justify-between text-sm text-gray-600 mb-2">
                <span>Uploading file…</span>
                <span>{state.uploadPercent}%</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-navy-600 rounded-full transition-all" style={{ width: `${state.uploadPercent}%` }} />
              </div>
            </div>
          )}

          {state.step === 'preprocessing' && (
            <p className="text-sm text-gray-500 text-center animate-pulse">
              {state.study?.source_type === 'pdf'
                ? 'Extracting text from PDF…'
                : 'Applying bandpass filter, 50Hz notch, epoch segmentation…'}
            </p>
          )}

          {state.step === 'analyzing' && state.epochTotal > 0 && (
            <div>
              <div className="flex justify-between text-sm text-gray-600 mb-2">
                <span>{state.study?.source_type === 'pdf' ? 'NLP extraction & depression scoring…' : 'MANAS-1 depression analysis…'}</span>
                <span>{state.epochProgress} / {state.epochTotal}</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full transition-all"
                  style={{ width: `${Math.round((state.epochProgress / state.epochTotal) * 100)}%` }}
                />
              </div>
            </div>
          )}

          {state.step === 'complete' && state.study && (
            <div className="text-center">
              <div className="text-5xl mb-3">✅</div>
              <p className="font-semibold text-green-700 mb-1">Analysis Complete</p>
              <p className="text-sm text-gray-500 mb-6">MANAS-1 has finished processing the EEG recording.</p>
              <button
                onClick={() => navigate(`/analysis/${state.study!.id}`)}
                className="bg-navy-600 text-white px-6 py-2.5 rounded-lg font-semibold hover:bg-navy-700 transition-colors"
              >
                View Analysis Results →
              </button>
            </div>
          )}
        </div>
      )}

      {state.step === 'error' && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <div className="text-4xl mb-3">⚠️</div>
          <p className="font-semibold text-red-700 mb-1">Analysis Failed</p>
          <p className="text-sm text-red-500 mb-4">{state.error}</p>
          <button onClick={reset} className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-red-700">
            Try Again
          </button>
        </div>
      )}
    </div>
  )
}
