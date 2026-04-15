import { useParams, useNavigate } from 'react-router-dom'
import { analysisApi } from '../api/analysis'

export default function ReportPage() {
  const { studyId } = useParams<{ studyId: string }>()
  const navigate = useNavigate()
  const sid = Number(studyId)
  const reportUrl = analysisApi.getReportUrl(sid)

  return (
    <div className="h-screen flex flex-col">
      <div className="bg-white border-b px-4 py-2 flex items-center gap-4 no-print">
        <button onClick={() => navigate(`/analysis/${sid}`)} className="text-navy-600 text-sm font-medium hover:underline">
          ← Back to Analysis
        </button>
        <span className="text-gray-400 text-sm flex-1">Clinical Report — Study #{sid}</span>
        <button
          onClick={() => window.print()}
          className="bg-navy-600 text-white px-4 py-1.5 rounded-lg text-sm font-semibold hover:bg-navy-700 transition-colors"
        >
          🖨️ Print / Save PDF
        </button>
      </div>
      <iframe
        src={reportUrl}
        className="flex-1 w-full border-0"
        title="Clinical Report"
      />
    </div>
  )
}
