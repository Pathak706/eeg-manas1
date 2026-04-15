import { Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import PatientListPage from './pages/PatientListPage'
import UploadPage from './pages/UploadPage'
import AnalysisPage from './pages/AnalysisPage'
import ReportPage from './pages/ReportPage'

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <nav className="bg-navy-600 text-white px-6 py-3 flex items-center justify-between shadow-lg">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🧠</span>
          <div>
            <div className="font-bold text-base leading-tight">EEG AI Platform</div>
            <div className="text-xs text-blue-200 leading-tight">Powered by MANAS-1 · Clinical Pre-Read</div>
          </div>
        </div>
        <div className="flex gap-6 text-sm font-medium">
          <NavLink
            to="/"
            className={({ isActive }) =>
              isActive ? 'text-white border-b-2 border-white pb-0.5' : 'text-blue-200 hover:text-white'
            }
            end
          >
            Patients
          </NavLink>
        </div>
      </nav>

      <main className="flex-1">
        <Routes>
          <Route path="/" element={<PatientListPage />} />
          <Route path="/upload/:patientId" element={<UploadPage />} />
          <Route path="/analysis/:studyId" element={<AnalysisPage />} />
          <Route path="/report/:studyId" element={<ReportPage />} />
        </Routes>
      </main>

      <footer className="bg-white border-t text-xs text-gray-400 px-6 py-3 text-center">
        EEG AI Platform × Intellihealth NeuroDx (MANAS-1) · POC v0.1 · For demonstration purposes only
      </footer>
    </div>
  )
}
