import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Play, Pause, X, Plus, RefreshCw, CheckCircle,
  AlertCircle, Clock, Loader2, Settings2, Target
} from 'lucide-react'
import { api } from '@/lib/api'

interface Scan {
  id: string
  name: string
  target_id: string
  status: string
  progress_percent: number
  total_requests: number
  total_endpoints: number
  total_parameters: number
  unique_parameters: number
  queue_size: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  pending:   { icon: <Clock size={13}/>,    color: 'text-slate-400',  label: 'Pending'   },
  running:   { icon: <Loader2 size={13} className="animate-spin"/>, color: 'text-cyan-400', label: 'Running' },
  paused:    { icon: <Pause size={13}/>,    color: 'text-amber-400',  label: 'Paused'    },
  completed: { icon: <CheckCircle size={13}/>, color: 'text-emerald-400', label: 'Completed' },
  failed:    { icon: <AlertCircle size={13}/>, color: 'text-red-400', label: 'Failed'    },
  cancelled: { icon: <X size={13}/>,        color: 'text-slate-500',  label: 'Cancelled' },
}

// ── New Scan Modal ─────────────────────────────────────────────────────────────

function NewScanModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('')
  const [targetUrl, setTargetUrl] = useState('')
  const [maxDepth, setMaxDepth] = useState(5)
  const [concurrency, setConcurrency] = useState(50)
  const [jsRendering, setJsRendering] = useState(true)
  const [respectRobots, setRespectRobots] = useState(true)
  const [error, setError] = useState('')

  const qc = useQueryClient()

  const createMutation = useMutation({
    mutationFn: async () => {
      // First create a temp project+target
      const projRes = await api.post('/projects/', { name: `Project: ${name}` })
      const projId = projRes.data.id
      const tgtRes = await api.post('/targets/', { project_id: projId, url: targetUrl })
      const tgtId = tgtRes.data.id
      return api.post('/scans/', {
        target_id: tgtId,
        name,
        config: {
          max_depth: maxDepth,
          concurrency,
          javascript_rendering: jsRendering,
          respect_robots_txt: respectRobots,
        },
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scans'] })
      onCreated()
      onClose()
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail ?? 'Failed to create scan')
    },
  })

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="w-full max-w-md bg-[#0D1520] border border-[#1E2A3A] rounded-xl p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold text-white">New Scan</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={16}/></button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-500 uppercase tracking-widest block mb-1.5">Scan Name</label>
            <input value={name} onChange={e => setName(e.target.value)}
              placeholder="Q1 API Audit"
              className="w-full bg-[#07101C] border border-[#1E2A3A] rounded-lg py-2 px-3 text-sm text-slate-200 placeholder:text-slate-700 focus:outline-none focus:border-cyan-500/50 font-mono"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 uppercase tracking-widest block mb-1.5">Target URL</label>
            <input value={targetUrl} onChange={e => setTargetUrl(e.target.value)}
              placeholder="https://example.com"
              className="w-full bg-[#07101C] border border-[#1E2A3A] rounded-lg py-2 px-3 text-sm text-slate-200 placeholder:text-slate-700 focus:outline-none focus:border-cyan-500/50 font-mono"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-widest block mb-1.5">Max Depth</label>
              <input type="number" value={maxDepth} onChange={e => setMaxDepth(+e.target.value)}
                min={1} max={20}
                className="w-full bg-[#07101C] border border-[#1E2A3A] rounded-lg py-2 px-3 text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 font-mono"
              />
            </div>
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-widest block mb-1.5">Concurrency</label>
              <input type="number" value={concurrency} onChange={e => setConcurrency(+e.target.value)}
                min={1} max={200}
                className="w-full bg-[#07101C] border border-[#1E2A3A] rounded-lg py-2 px-3 text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 font-mono"
              />
            </div>
          </div>
          <div className="flex gap-6 pt-1">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={jsRendering} onChange={e => setJsRendering(e.target.checked)} className="accent-cyan-500" />
              <span className="text-xs text-slate-400">JS Rendering</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={respectRobots} onChange={e => setRespectRobots(e.target.checked)} className="accent-cyan-500" />
              <span className="text-xs text-slate-400">Respect robots.txt</span>
            </label>
          </div>

          {error && (
            <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>

        <div className="flex gap-3 mt-6">
          <button onClick={onClose}
            className="flex-1 py-2 text-sm border border-[#1E2A3A] text-slate-400 hover:text-white rounded-lg transition-colors">
            Cancel
          </button>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!name || !targetUrl || createMutation.isPending}
            className="flex-1 py-2 text-sm bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded-lg transition-colors font-medium"
          >
            {createMutation.isPending ? 'Creating...' : 'Launch Scan'}
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

// ── Scan Card ──────────────────────────────────────────────────────────────────

function ScanCard({ scan, onAction }: { scan: Scan; onAction: () => void }) {
  const cfg = STATUS_CONFIG[scan.status] ?? STATUS_CONFIG.pending
  const qc = useQueryClient()

  const pauseMutation = useMutation({
    mutationFn: () => api.post(`/scans/${scan.id}/pause`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scans'] }); onAction() },
  })
  const resumeMutation = useMutation({
    mutationFn: () => api.post(`/scans/${scan.id}/resume`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scans'] }); onAction() },
  })
  const cancelMutation = useMutation({
    mutationFn: () => api.post(`/scans/${scan.id}/cancel`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scans'] }); onAction() },
  })

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-[#0D1520] border border-[#1E2A3A] rounded-xl p-5 hover:border-[#2D3F52] transition-colors"
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-white text-sm truncate">{scan.name}</h3>
          <p className="text-xs font-mono text-slate-600 mt-0.5 truncate">ID: {scan.id.slice(0, 8)}...</p>
        </div>
        <div className={`flex items-center gap-1.5 text-xs font-mono ${cfg.color} flex-shrink-0`}>
          {cfg.icon}
          {cfg.label}
        </div>
      </div>

      {/* Progress */}
      {(scan.status === 'running' || scan.status === 'paused') && (
        <div className="mb-4">
          <div className="flex justify-between text-xs text-slate-500 mb-1.5 font-mono">
            <span>{scan.progress_percent.toFixed(1)}%</span>
            <span>Queue: {scan.queue_size.toLocaleString()}</span>
          </div>
          <div className="h-1.5 bg-[#1E2A3A] rounded-full overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500"
              animate={{ width: `${scan.progress_percent}%` }}
              transition={{ duration: 0.8 }}
            />
          </div>
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        {[
          { label: 'Requests', value: scan.total_requests },
          { label: 'Endpoints', value: scan.total_endpoints },
          { label: 'Params', value: scan.total_parameters },
          { label: 'Unique', value: scan.unique_parameters },
        ].map(s => (
          <div key={s.label} className="text-center">
            <p className="text-base font-bold font-mono text-cyan-300">{s.value.toLocaleString()}</p>
            <p className="text-[10px] text-slate-600 uppercase tracking-wide">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Error */}
      {scan.error_message && (
        <p className="text-xs text-red-400 bg-red-500/10 rounded px-2 py-1 mb-3 font-mono truncate">
          {scan.error_message}
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-2 pt-3 border-t border-[#1E2A3A]">
        {scan.status === 'running' && (
          <button onClick={() => pauseMutation.mutate()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-[#1E2A3A] text-amber-400 hover:bg-amber-500/10 rounded transition-colors">
            <Pause size={11}/> Pause
          </button>
        )}
        {scan.status === 'paused' && (
          <button onClick={() => resumeMutation.mutate()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-[#1E2A3A] text-cyan-400 hover:bg-cyan-500/10 rounded transition-colors">
            <Play size={11}/> Resume
          </button>
        )}
        {['running', 'paused', 'pending'].includes(scan.status) && (
          <button onClick={() => cancelMutation.mutate()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-[#1E2A3A] text-red-400 hover:bg-red-500/10 rounded transition-colors">
            <X size={11}/> Cancel
          </button>
        )}
        <span className="ml-auto text-[10px] font-mono text-slate-600">
          {scan.started_at ? new Date(scan.started_at).toLocaleString() : new Date(scan.created_at).toLocaleString()}
        </span>
      </div>
    </motion.div>
  )
}

// ── Main Scans Page ────────────────────────────────────────────────────────────

export default function ScansPage() {
  const [showModal, setShowModal] = useState(false)
  const qc = useQueryClient()

  const { data, isLoading } = useQuery<{ items: Scan[] }>({
    queryKey: ['scans'],
    queryFn: () => api.get('/scans/').then(r => r.data),
    refetchInterval: 5000,
  })

  const scans = data?.items ?? []
  const running = scans.filter(s => s.status === 'running')
  const rest = scans.filter(s => s.status !== 'running')

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Scans</h1>
          <p className="text-sm text-slate-500 font-mono mt-0.5">
            {running.length} running · {scans.length} total
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => qc.invalidateQueries({ queryKey: ['scans'] })}
            className="cyber-btn flex items-center gap-2">
            <RefreshCw size={13}/> Refresh
          </button>
          <button onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 text-sm bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg font-medium transition-colors">
            <Plus size={14}/> New Scan
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Loader2 size={24} className="animate-spin text-cyan-400" />
        </div>
      )}

      {!isLoading && scans.length === 0 && (
        <div className="text-center py-16">
          <Target size={40} className="text-slate-700 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">No scans yet. Launch your first scan.</p>
          <button onClick={() => setShowModal(true)}
            className="mt-4 px-4 py-2 text-sm bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors">
            Launch Scan
          </button>
        </div>
      )}

      {running.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">
            Active Scans
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {running.map(s => (
              <ScanCard key={s.id} scan={s} onAction={() => qc.invalidateQueries({ queryKey: ['scans'] })} />
            ))}
          </div>
        </div>
      )}

      {rest.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">
            Scan History
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {rest.map(s => (
              <ScanCard key={s.id} scan={s} onAction={() => qc.invalidateQueries({ queryKey: ['scans'] })} />
            ))}
          </div>
        </div>
      )}

      <AnimatePresence>
        {showModal && (
          <NewScanModal
            onClose={() => setShowModal(false)}
            onCreated={() => qc.invalidateQueries({ queryKey: ['scans'] })}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
