import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import {
  Search, Globe, Zap, Wifi, Code2, ExternalLink,
  ChevronDown, ChevronRight, Activity
} from 'lucide-react'
import { api } from '@/lib/api'

interface EndpointItem {
  id: string
  url: string
  path: string
  domain: string
  method: string
  status_code: number | null
  content_type: string | null
  response_time_ms: number | null
  is_api: boolean
  is_graphql: boolean
  is_websocket: boolean
  framework_detected: string | null
  parameter_count: number
  first_seen: string
}

const METHOD_COLORS: Record<string, string> = {
  GET: 'text-emerald-400 bg-emerald-500/10',
  POST: 'text-blue-400 bg-blue-500/10',
  PUT: 'text-amber-400 bg-amber-500/10',
  PATCH: 'text-purple-400 bg-purple-500/10',
  DELETE: 'text-red-400 bg-red-500/10',
}

function StatusBadge({ code }: { code: number | null }) {
  if (!code) return <span className="text-slate-600 text-xs font-mono">—</span>
  let color = 'text-slate-400'
  if (code < 300) color = 'text-emerald-400'
  else if (code < 400) color = 'text-cyan-400'
  else if (code < 500) color = 'text-amber-400'
  else color = 'text-red-400'
  return <span className={`text-xs font-mono font-semibold ${color}`}>{code}</span>
}

function TypeIcon({ ep }: { ep: EndpointItem }) {
  if (ep.is_graphql) return <span title="GraphQL"><Zap size={13} className="text-purple-400" /></span>
  if (ep.is_websocket) return <span title="WebSocket"><Wifi size={13} className="text-pink-400" /></span>
  if (ep.is_api) return <span title="REST API"><Code2 size={13} className="text-cyan-400" /></span>
  return <span title="Page"><Globe size={13} className="text-slate-500" /></span>
}

// Mock data
const MOCK_ENDPOINTS: EndpointItem[] = Array.from({ length: 60 }, (_, i) => {
  const paths = [
    '/api/v1/users', '/api/v1/users/{id}', '/api/v1/products', '/api/v1/products/search',
    '/api/v1/orders', '/api/v1/orders/{id}/items', '/api/v1/auth/login', '/api/v1/auth/refresh',
    '/graphql', '/ws/notifications', '/api/v2/cart', '/admin/dashboard', '/api/v1/upload',
    '/api/v1/reports/export', '/.well-known/openapi.json'
  ]
  const methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
  const path = paths[i % paths.length]
  return {
    id: `ep-${i}`,
    url: `https://api.example.com${path}`,
    path,
    domain: 'api.example.com',
    method: methods[i % methods.length],
    status_code: [200, 200, 201, 204, 401, 404, 500][i % 7],
    content_type: 'application/json',
    response_time_ms: Math.floor(Math.random() * 800) + 50,
    is_api: !path.includes('graphql') && !path.includes('ws/'),
    is_graphql: path.includes('graphql'),
    is_websocket: path.includes('ws/'),
    framework_detected: i % 5 === 0 ? 'FastAPI' : i % 7 === 0 ? 'Express.js' : null,
    parameter_count: Math.floor(Math.random() * 40) + 1,
    first_seen: new Date(Date.now() - Math.random() * 86400000 * 10).toISOString(),
  }
})

export default function EndpointsPage() {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<'all' | 'api' | 'graphql' | 'websocket'>('all')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const { data } = useQuery<{ items: EndpointItem[]; total: number }>({
    queryKey: ['endpoints'],
    queryFn: () => api.get('/endpoints/').then(r => r.data),
  })

  const endpoints = data?.items?.length ? data.items : MOCK_ENDPOINTS

  const filtered = useMemo(() => {
    let list = endpoints
    if (filter === 'api') list = list.filter(e => e.is_api && !e.is_graphql && !e.is_websocket)
    if (filter === 'graphql') list = list.filter(e => e.is_graphql)
    if (filter === 'websocket') list = list.filter(e => e.is_websocket)
    if (search) {
      const s = search.toLowerCase()
      list = list.filter(e => e.path.toLowerCase().includes(s) || e.domain.toLowerCase().includes(s))
    }
    return list
  }, [endpoints, filter, search])

  const toggleExpand = (id: string) => {
    const next = new Set(expanded)
    next.has(id) ? next.delete(id) : next.add(id)
    setExpanded(next)
  }

  const counts = {
    all: endpoints.length,
    api: endpoints.filter(e => e.is_api && !e.is_graphql && !e.is_websocket).length,
    graphql: endpoints.filter(e => e.is_graphql).length,
    websocket: endpoints.filter(e => e.is_websocket).length,
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Endpoint Inventory</h1>
          <p className="text-sm text-slate-500 font-mono mt-0.5">{filtered.length} endpoints</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={15} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by path or domain..."
            className="cyber-input pl-9 font-mono"
          />
        </div>
        <div className="flex gap-1 bg-[#0D1520] border border-[#1E2A3A] rounded-lg p-1">
          {[
            { key: 'all', label: 'All', icon: <Globe size={12}/> },
            { key: 'api', label: 'REST', icon: <Code2 size={12}/> },
            { key: 'graphql', label: 'GraphQL', icon: <Zap size={12}/> },
            { key: 'websocket', label: 'WebSocket', icon: <Wifi size={12}/> },
          ].map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key as any)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-all ${
                filter === f.key ? 'bg-cyan-500/15 text-cyan-400' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {f.icon} {f.label}
              <span className="font-mono text-[10px] text-slate-600">{counts[f.key as keyof typeof counts]}</span>
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="space-y-1.5">
        {filtered.map((ep, i) => (
          <motion.div
            key={ep.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(i * 0.01, 0.3) }}
            className="bg-[#0D1520] border border-[#1E2A3A] rounded-lg overflow-hidden hover:border-[#2D3F52] transition-colors"
          >
            <button
              onClick={() => toggleExpand(ep.id)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left"
            >
              {expanded.has(ep.id) ? <ChevronDown size={14} className="text-slate-500 flex-shrink-0"/> : <ChevronRight size={14} className="text-slate-500 flex-shrink-0"/>}
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${METHOD_COLORS[ep.method] || 'text-slate-400 bg-slate-500/10'}`}>
                {ep.method}
              </span>
              <TypeIcon ep={ep} />
              <span className="font-mono text-sm text-slate-200 flex-1 truncate">{ep.path}</span>
              {ep.framework_detected && (
                <span className="text-[10px] font-mono text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded flex-shrink-0">
                  {ep.framework_detected}
                </span>
              )}
              <StatusBadge code={ep.status_code} />
              <span className="text-xs font-mono text-slate-500 w-16 text-right flex-shrink-0">
                {ep.response_time_ms}ms
              </span>
              <span className="text-xs font-mono text-cyan-400 w-20 text-right flex-shrink-0">
                {ep.parameter_count} params
              </span>
            </button>

            {expanded.has(ep.id) && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="px-4 pb-4 pt-1 border-t border-[#1E2A3A] ml-7"
              >
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                  <div>
                    <p className="text-slate-600 uppercase tracking-widest text-[10px] mb-1">Full URL</p>
                    <p className="font-mono text-slate-300 truncate flex items-center gap-1">
                      {ep.url} <ExternalLink size={10} className="text-slate-600"/>
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-600 uppercase tracking-widest text-[10px] mb-1">Content Type</p>
                    <p className="font-mono text-slate-300">{ep.content_type ?? '—'}</p>
                  </div>
                  <div>
                    <p className="text-slate-600 uppercase tracking-widest text-[10px] mb-1">First Seen</p>
                    <p className="font-mono text-slate-300">{new Date(ep.first_seen).toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-slate-600 uppercase tracking-widest text-[10px] mb-1">Response Time</p>
                    <p className="font-mono text-slate-300 flex items-center gap-1">
                      <Activity size={11} className="text-cyan-400"/> {ep.response_time_ms}ms
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </motion.div>
        ))}
      </div>
    </div>
  )
}
