import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { patientsApi } from '../api/patients'
import { studiesApi } from '../api/studies'
import type { Patient, PatientCreate } from '../types'

export default function PatientListPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const { data: patients = [], isLoading } = useQuery({
    queryKey: ['patients', search],
    queryFn: () => patientsApi.list(search),
  })

  const { data: studies = [] } = useQuery({
    queryKey: ['studies', expandedId],
    queryFn: () => studiesApi.listForPatient(expandedId!),
    enabled: expandedId !== null,
  })

  const createMutation = useMutation({
    mutationFn: patientsApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['patients'] })
      setShowForm(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: patientsApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['patients'] }),
  })

  return (
    <div className="max-w-5xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-navy-600">Patient Registry</h1>
          <p className="text-sm text-gray-500 mt-1">{patients.length} patient{patients.length !== 1 ? 's' : ''} registered</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="bg-navy-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-navy-700 transition-colors"
        >
          + New Patient
        </button>
      </div>

      <div className="mb-4">
        <input
          type="text"
          placeholder="Search by name or MRN…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy-600"
        />
      </div>

      {isLoading ? (
        <div className="text-center py-16 text-gray-400">Loading patients…</div>
      ) : patients.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-3">🧬</div>
          <p className="text-gray-500 font-medium">No patients yet</p>
          <p className="text-gray-400 text-sm mt-1">Create a patient to start an EEG analysis</p>
          <button
            onClick={() => setShowForm(true)}
            className="mt-4 bg-navy-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-navy-700"
          >
            Add First Patient
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-navy-600 text-white">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wide">Name</th>
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wide">MRN</th>
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wide">DOB</th>
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wide">Gender</th>
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wide">Studies</th>
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wide">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {patients.map((p) => (
                <>
                  <tr
                    key={p.id}
                    className="hover:bg-blue-50 cursor-pointer transition-colors"
                    onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}
                  >
                    <td className="px-4 py-3 font-medium">{p.name}</td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{p.mrn}</td>
                    <td className="px-4 py-3 text-gray-500">{p.date_of_birth}</td>
                    <td className="px-4 py-3 text-gray-500">{p.gender}</td>
                    <td className="px-4 py-3">
                      <span className="bg-blue-100 text-blue-800 text-xs font-semibold px-2 py-0.5 rounded-full">
                        {p.study_count}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={(e) => { e.stopPropagation(); navigate(`/upload/${p.id}`) }}
                        className="text-navy-600 font-semibold hover:underline text-xs mr-3"
                      >
                        New EEG
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); if (confirm('Delete patient?')) deleteMutation.mutate(p.id) }}
                        className="text-red-400 hover:text-red-600 text-xs"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                  {expandedId === p.id && (
                    <tr key={`${p.id}-studies`}>
                      <td colSpan={6} className="px-4 pb-4 pt-2 bg-blue-50">
                        <div className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">EEG Studies</div>
                        {studies.length === 0 ? (
                          <p className="text-xs text-gray-400">No studies yet for this patient.</p>
                        ) : (
                          <div className="flex flex-col gap-2">
                            {studies.map((s) => (
                              <div
                                key={s.id}
                                className="flex items-center gap-4 bg-white rounded-lg px-3 py-2 border border-gray-100 cursor-pointer hover:border-navy-600 transition-colors"
                                onClick={() => s.status === 'complete' && navigate(`/analysis/${s.id}`)}
                              >
                                <div className="text-xs text-gray-500 w-36">{new Date(s.study_date).toLocaleDateString()}</div>
                                <div className="text-xs text-gray-500">{s.recording_duration_sec.toFixed(0)}s · {s.channel_count} ch</div>
                                {s.is_synthetic && <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-medium">Demo</span>}
                                <StatusBadge status={s.status} />
                                {s.status === 'complete' && (
                                  <button
                                    className="ml-auto text-xs text-navy-600 font-semibold hover:underline"
                                    onClick={(e) => { e.stopPropagation(); navigate(`/analysis/${s.id}`) }}
                                  >
                                    View Analysis →
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                        <button
                          onClick={() => navigate(`/upload/${p.id}`)}
                          className="mt-3 text-xs bg-navy-600 text-white px-3 py-1.5 rounded-lg font-semibold hover:bg-navy-700"
                        >
                          + New EEG Study
                        </button>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && <NewPatientModal onClose={() => setShowForm(false)} onCreate={(d) => createMutation.mutate(d)} loading={createMutation.isPending} />}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    uploaded: 'bg-gray-100 text-gray-600',
    preprocessing: 'bg-yellow-100 text-yellow-700',
    analyzing: 'bg-blue-100 text-blue-700',
    complete: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${map[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}

function NewPatientModal({ onClose, onCreate, loading }: { onClose: () => void; onCreate: (d: PatientCreate) => void; loading: boolean }) {
  const [form, setForm] = useState<PatientCreate>({
    mrn: '',
    name: '',
    date_of_birth: '',
    gender: 'Male',
    referring_physician: '',
  })

  const set = (k: keyof PatientCreate) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((prev) => ({ ...prev, [k]: e.target.value }))

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6">
        <h2 className="text-lg font-bold text-navy-600 mb-4">New Patient</h2>
        <div className="space-y-3">
          <Field label="Full Name *"><input className={input} value={form.name} onChange={set('name')} placeholder="e.g. Aarav Sharma" /></Field>
          <Field label="MRN *"><input className={input} value={form.mrn} onChange={set('mrn')} placeholder="e.g. MRN-2024-001" /></Field>
          <Field label="Date of Birth *"><input className={input} type="date" value={form.date_of_birth} onChange={set('date_of_birth')} /></Field>
          <Field label="Gender">
            <select className={input} value={form.gender} onChange={set('gender')}>
              <option>Male</option><option>Female</option><option>Other</option>
            </select>
          </Field>
          <Field label="Referring Physician"><input className={input} value={form.referring_physician} onChange={set('referring_physician')} placeholder="Dr. Name" /></Field>
        </div>
        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="flex-1 border border-gray-200 rounded-lg py-2 text-sm font-medium hover:bg-gray-50">Cancel</button>
          <button
            onClick={() => onCreate(form)}
            disabled={loading || !form.name || !form.mrn || !form.date_of_birth}
            className="flex-1 bg-navy-600 text-white rounded-lg py-2 text-sm font-semibold hover:bg-navy-700 disabled:opacity-50"
          >
            {loading ? 'Creating…' : 'Create Patient'}
          </button>
        </div>
      </div>
    </div>
  )
}

const input = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy-600'
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="block text-xs font-semibold text-gray-600 mb-1">{label}</label>{children}</div>
}
