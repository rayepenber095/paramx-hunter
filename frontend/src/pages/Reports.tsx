import { useState } from 'react'
import { motion } from 'framer-motion'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  FileText, FileJson, FileSpreadsheet, File,
  Download, Loader2, CheckCircle, Eye, EyeOff
} from 'lucide-react'
import { api } from '@/lib/api'

interface Scan {
  id: string
  name: string
  status: string
  total_parameters: number
  total_endpoints: number
}

const FORMATS = [
  { id: 'pdf', label: 'PDF Report', icon: <FileText size={20} />, desc: 'Executive & technical summary, print-ready', color: '#ef4444' },
  { id: 'html', label: 'HTML Report', icon: <File size={20} />, desc: 'Interactive dark-themed report for sharing', color: '#06b6d4' },
  { id: 'excel', label: 'Excel Workbook', icon: <FileSpreadsheet size={20} />, desc: 'Multi-sheet spreadsheet with raw data', color: '#10b981' },
  { id: 'json', label: 'JSON Export', icon: <FileJson size={20} />, desc: 'Machine-readable, full parameter detail', color: '#f59e0b' },
]

const MOCK_SCANS: Scan[] = [
  { id: 'scan-1', name: 'Production API Audit Q1', status: 'completed', total_parameters: 8432, total_endpoints: 312 },
  { id: 'scan-2', name: 'Staging Deep Scan', status: 'completed', total_parameters: 4218, total_endpoints: 184 },
  { id: 'scan-3', name: 'Mobile API Discovery', status: 'completed', total_parameters: 1942, total_endpoints: 97 },
]

export default function ReportsPage() {
  const [selectedScan, setSelectedScan] = useState<string>('')
  const [selectedFormat, setSelectedFormat] = useState<string>('pdf')
  const [includeValues, setIncludeValues] = useState(false)
  const [generated, setGenerated] = useState<{ jobId: string; format: string } | null>(null)

  const { data } = useQuery<{ items: Scan[] }>({
    queryKey: ['scans-for-reports'],
    queryFn: () => api.get('/scans/?status=completed').then(r => r.data),
  })

  const scans = data?.items?.length ? data.items : MOCK_SCANS

  const generateMutation = useMutation({
    mutationFn: () => api.post('/reports/generate', {
      scan_id: selectedScan,
      format: selectedFormat,
      include_values: includeValues,
    }),
    onSuccess: (res) => {
      setGenerated({ jobId: res.data.job_id, format: selectedFormat })
    },
  })

  const downloadUrl = generated ? `/api/v1/reports/download/${generated.jobId}` : null

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Reports</h1>
        <p className="text-sm text-slate-500 font-mono mt-0.5">
          Generate executive & technical reports from completed scans
        </p>
      </div>

      {/* Scan selector */}
      <div className="cyber-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-widest mb-4">
          1. Select Scan
        </h3>
        <div className="space-y-2">
          {scans.map(scan => (
            <button
              key={scan.id}
              onClick={() => setSelectedScan(scan.id)}
              className={`w-full flex items-center justify-between p-3 rounded-lg border text-left transition-all ${
                selectedScan === scan.id
                  ? 'border-cyan-500/40 bg-cyan-500/5'
                  : 'border-[#1E2A3A] hover:border-[#2D3F52]'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${selectedScan === scan.id ? 'bg-cyan-400' : 'bg-slate-700'}`} />
                <div>
                  <p className="text-sm font-medium text-slate-200">{scan.name}</p>
                  <p className="text-xs text-slate-600 font-mono mt-0.5">
                    {scan.total_endpoints} endpoints · {scan.total_parameters.toLocaleString()} parameters
                  </p>
                </div>
              </div>
              {selectedScan === scan.id && <CheckCircle size={16} className="text-cyan-400" />}
            </button>
          ))}
        </div>
      </div>

      {/* Format selector */}
      <div className="cyber-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-widest mb-4">
          2. Choose Format
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {FORMATS.map(fmt => (
            <button
              key={fmt.id}
              onClick={() => setSelectedFormat(fmt.id)}
              className={`flex flex-col items-start gap-2 p-4 rounded-lg border text-left transition-all ${
                selectedFormat === fmt.id
                  ? 'border-cyan-500/40 bg-cyan-500/5'
                  : 'border-[#1E2A3A] hover:border-[#2D3F52]'
              }`}
            >
              <div style={{ color: fmt.color }}>{fmt.icon}</div>
              <div>
                <p className="text-sm font-medium text-slate-200">{fmt.label}</p>
                <p className="text-xs text-slate-600 mt-0.5">{fmt.desc}</p>
              </div>
            </button>
          ))}
        </div>

        {/* Options */}
        <div className="mt-4 pt-4 border-t border-[#1E2A3A]">
          <label className="flex items-center gap-3 cursor-pointer">
            <button
              onClick={() => setIncludeValues(!includeValues)}
              className={`w-9 h-5 rounded-full transition-colors relative ${includeValues ? 'bg-cyan-600' : 'bg-[#1E2A3A]'}`}
            >
              <motion.div
                className="w-3.5 h-3.5 rounded-full bg-white absolute top-0.75"
                animate={{ left: includeValues ? 18 : 3 }}
                style={{ top: 3 }}
              />
            </button>
            <div className="flex items-center gap-2">
              {includeValues ? <Eye size={13} className="text-cyan-400"/> : <EyeOff size={13} className="text-slate-500"/>}
              <span className="text-sm text-slate-300">Include actual parameter values</span>
            </div>
          </label>
          <p className="text-xs text-slate-600 mt-1.5 ml-12">
            ⚠ Values may contain sensitive data. Only enable for internal reports.
          </p>
        </div>
      </div>

      {/* Generate */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => generateMutation.mutate()}
          disabled={!selectedScan || generateMutation.isPending}
          className="flex items-center gap-2 px-6 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium text-sm rounded-lg transition-colors"
        >
          {generateMutation.isPending ? (
            <><Loader2 size={14} className="animate-spin"/> Generating...</>
          ) : (
            <><FileText size={14}/> Generate Report</>
          )}
        </button>

        {downloadUrl && (
          <motion.a
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            href={downloadUrl}
            download
            className="flex items-center gap-2 px-6 py-2.5 border border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10 text-sm font-medium rounded-lg transition-colors"
          >
            <Download size={14}/> Download {generated?.format.toUpperCase()}
          </motion.a>
        )}
      </div>

      {/* Quick exports */}
      {selectedScan && (
        <div className="cyber-card p-5">
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-widest mb-3">
            Quick Data Export
          </h3>
          <div className="flex gap-3">
            <a
              href={`/api/v1/parameters/export/csv?scan_id=${selectedScan}`}
              className="cyber-btn flex items-center gap-2"
            >
              <Download size={13}/> Parameters CSV
            </a>
            <a
              href={`/api/v1/parameters/export/json?scan_id=${selectedScan}`}
              className="cyber-btn flex items-center gap-2"
            >
              <Download size={13}/> Parameters JSON
            </a>
            <a
              href={`/api/v1/reports/quick-json/${selectedScan}`}
              className="cyber-btn flex items-center gap-2"
            >
              <Download size={13}/> Full Scan JSON
            </a>
          </div>
        </div>
      )}
    </div>
  )
}
