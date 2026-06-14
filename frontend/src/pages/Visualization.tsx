import { useState, useMemo, useCallback } from 'react'
import { motion } from 'framer-motion'
import ReactFlow, {
  Background, Controls, MiniMap, Node, Edge,
  useNodesState, useEdgesState, MarkerType, Position,
  Handle, NodeProps,
} from 'reactflow'
import 'reactflow/dist/style.css'
import {
  Network, GitBranch, Key, Cookie, Shield,
  Globe, Hash, Lock, Workflow
} from 'lucide-react'

// ── Custom Node Components ──────────────────────────────────────────────────

function EndpointNode({ data }: NodeProps) {
  return (
    <div className="rounded-lg border border-cyan-500/40 bg-[#0D1520] px-4 py-2.5 shadow-lg shadow-cyan-500/5 min-w-[160px]">
      <Handle type="target" position={Position.Left} className="!bg-cyan-500 !w-2 !h-2" />
      <Handle type="source" position={Position.Right} className="!bg-cyan-500 !w-2 !h-2" />
      <div className="flex items-center gap-2 mb-1">
        <Globe size={12} className="text-cyan-400" />
        <span className="text-[10px] font-mono font-bold text-cyan-400 uppercase">{data.method}</span>
      </div>
      <p className="text-xs font-mono text-slate-200 truncate">{data.label}</p>
      {data.paramCount && (
        <p className="text-[10px] text-slate-600 font-mono mt-1">{data.paramCount} params</p>
      )}
    </div>
  )
}

function ParamNode({ data }: NodeProps) {
  const iconMap: Record<string, React.ReactNode> = {
    auth: <Lock size={11} className="text-red-400" />,
    cookie: <Cookie size={11} className="text-pink-400" />,
    key: <Key size={11} className="text-amber-400" />,
    default: <Hash size={11} className="text-purple-400" />,
  }
  return (
    <div className={`rounded-lg border px-3 py-2 bg-[#0D1520] min-w-[120px] ${
      data.risk === 'critical' || data.risk === 'high'
        ? 'border-red-500/40 shadow-lg shadow-red-500/10'
        : 'border-purple-500/30'
    }`}>
      <Handle type="target" position={Position.Left} className="!bg-purple-500 !w-2 !h-2" />
      <div className="flex items-center gap-2">
        {iconMap[data.icon] ?? iconMap.default}
        <span className="text-xs font-mono text-slate-200 truncate">{data.label}</span>
      </div>
      {data.risk && (
        <span className={`text-[9px] font-mono uppercase mt-1 inline-block px-1.5 py-0.5 rounded ${
          data.risk === 'critical' ? 'bg-red-500/15 text-red-400' :
          data.risk === 'high' ? 'bg-orange-500/15 text-orange-400' :
          'bg-blue-500/15 text-blue-400'
        }`}>
          {data.risk}
        </span>
      )}
    </div>
  )
}

function AuthNode({ data }: NodeProps) {
  return (
    <div className="rounded-lg border-2 border-emerald-500/50 bg-emerald-500/5 px-4 py-3 min-w-[140px]">
      <Handle type="target" position={Position.Top} className="!bg-emerald-500 !w-2 !h-2" />
      <Handle type="source" position={Position.Bottom} className="!bg-emerald-500 !w-2 !h-2" />
      <div className="flex items-center gap-2">
        <Shield size={13} className="text-emerald-400" />
        <span className="text-xs font-semibold text-emerald-300">{data.label}</span>
      </div>
    </div>
  )
}

const nodeTypes = {
  endpoint: EndpointNode,
  param: ParamNode,
  auth: AuthNode,
}

// ── Endpoint Graph Data ───────────────────────────────────────────────────────

function buildEndpointGraph(): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [
    { id: 'login', type: 'endpoint', position: { x: 0, y: 100 },
      data: { label: '/api/v1/auth/login', method: 'POST', paramCount: 4 } },
    { id: 'refresh', type: 'endpoint', position: { x: 0, y: 250 },
      data: { label: '/api/v1/auth/refresh', method: 'POST', paramCount: 2 } },
    { id: 'users', type: 'endpoint', position: { x: 320, y: 0 },
      data: { label: '/api/v1/users', method: 'GET', paramCount: 8 } },
    { id: 'userDetail', type: 'endpoint', position: { x: 320, y: 130 },
      data: { label: '/api/v1/users/{id}', method: 'GET', paramCount: 6 } },
    { id: 'orders', type: 'endpoint', position: { x: 320, y: 260 },
      data: { label: '/api/v1/orders', method: 'GET', paramCount: 12 } },
    { id: 'graphql', type: 'endpoint', position: { x: 320, y: 390 },
      data: { label: '/graphql', method: 'POST', paramCount: 31 } },
    { id: 'token', type: 'param', position: { x: 620, y: 60 },
      data: { label: 'Authorization', icon: 'auth', risk: 'high' } },
    { id: 'userId', type: 'param', position: { x: 620, y: 150 },
      data: { label: 'user_id', icon: 'default' } },
    { id: 'apiKey', type: 'param', position: { x: 620, y: 240 },
      data: { label: 'api_key', icon: 'key', risk: 'critical' } },
    { id: 'sessionCookie', type: 'param', position: { x: 620, y: 330 },
      data: { label: 'session_id', icon: 'cookie' } },
  ]

  const edges: Edge[] = [
    { id: 'e1', source: 'login', target: 'token', animated: true,
      style: { stroke: '#06b6d4' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#06b6d4' } },
    { id: 'e2', source: 'token', target: 'users', animated: true,
      style: { stroke: '#8b5cf6' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#8b5cf6' } },
    { id: 'e3', source: 'token', target: 'userDetail',
      style: { stroke: '#8b5cf6' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#8b5cf6' } },
    { id: 'e4', source: 'users', target: 'userId',
      style: { stroke: '#475569' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#475569' } },
    { id: 'e5', source: 'userDetail', target: 'userId',
      style: { stroke: '#475569' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#475569' } },
    { id: 'e6', source: 'orders', target: 'apiKey',
      style: { stroke: '#ef4444' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#ef4444' } },
    { id: 'e7', source: 'refresh', target: 'sessionCookie',
      style: { stroke: '#ec4899' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#ec4899' } },
    { id: 'e8', source: 'graphql', target: 'token',
      style: { stroke: '#8b5cf6' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#8b5cf6' } },
    { id: 'e9', source: 'graphql', target: 'sessionCookie',
      style: { stroke: '#ec4899' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#ec4899' } },
  ]

  return { nodes, edges }
}

// ── Auth Flow Graph Data ───────────────────────────────────────────────────────

function buildAuthFlowGraph(): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [
    { id: 'a1', type: 'auth', position: { x: 250, y: 0 }, data: { label: 'POST /auth/login' } },
    { id: 'a2', type: 'param', position: { x: 250, y: 110 }, data: { label: 'access_token (JWT)', icon: 'auth' } },
    { id: 'a3', type: 'param', position: { x: 60, y: 220 }, data: { label: 'refresh_token', icon: 'cookie' } },
    { id: 'a4', type: 'auth', position: { x: 250, y: 330 }, data: { label: 'Authorization: Bearer' } },
    { id: 'a5', type: 'endpoint', position: { x: 480, y: 220 },
      data: { label: '/api/v1/*', method: 'ANY' } },
    { id: 'a6', type: 'auth', position: { x: 60, y: 110 }, data: { label: 'POST /auth/refresh' } },
  ]

  const edges: Edge[] = [
    { id: 'ea1', source: 'a1', target: 'a2', animated: true,
      style: { stroke: '#10b981' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#10b981' } },
    { id: 'ea2', source: 'a1', target: 'a3',
      style: { stroke: '#10b981' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#10b981' } },
    { id: 'ea3', source: 'a2', target: 'a4', animated: true,
      style: { stroke: '#06b6d4' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#06b6d4' } },
    { id: 'ea4', source: 'a4', target: 'a5', animated: true,
      style: { stroke: '#06b6d4' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#06b6d4' } },
    { id: 'ea5', source: 'a3', target: 'a6',
      style: { stroke: '#ec4899' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#ec4899' } },
    { id: 'ea6', source: 'a6', target: 'a2', animated: true,
      style: { stroke: '#10b981', strokeDasharray: '4 4' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#10b981' } },
  ]

  return { nodes, edges }
}

// ── Cookie Flow Diagram ─────────────────────────────────────────────────────────

function buildCookieFlow(): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [
    { id: 'c1', type: 'endpoint', position: { x: 0, y: 0 }, data: { label: 'GET /', method: 'GET' } },
    { id: 'c2', type: 'param', position: { x: 280, y: -60 }, data: { label: '_ga (tracking)', icon: 'cookie' } },
    { id: 'c3', type: 'param', position: { x: 280, y: 30 }, data: { label: 'session_id (HttpOnly)', icon: 'cookie', risk: 'high' } },
    { id: 'c4', type: 'param', position: { x: 280, y: 120 }, data: { label: 'csrf_token', icon: 'cookie' } },
    { id: 'c5', type: 'endpoint', position: { x: 560, y: 0 }, data: { label: 'POST /api/v1/checkout', method: 'POST' } },
    { id: 'c6', type: 'endpoint', position: { x: 560, y: 150 }, data: { label: 'GET /api/v1/profile', method: 'GET' } },
  ]
  const edges: Edge[] = [
    { id: 'ec1', source: 'c1', target: 'c2', style: { stroke: '#ec4899' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#ec4899' } },
    { id: 'ec2', source: 'c1', target: 'c3', style: { stroke: '#ec4899' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#ec4899' } },
    { id: 'ec3', source: 'c1', target: 'c4', style: { stroke: '#ec4899' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#ec4899' } },
    { id: 'ec4', source: 'c3', target: 'c5', animated: true, style: { stroke: '#06b6d4' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#06b6d4' } },
    { id: 'ec5', source: 'c4', target: 'c5', style: { stroke: '#475569' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#475569' } },
    { id: 'ec6', source: 'c3', target: 'c6', animated: true, style: { stroke: '#06b6d4' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#06b6d4' } },
  ]
  return { nodes, edges }
}

// ── Tab Config ─────────────────────────────────────────────────────────────────

const GRAPH_TABS = [
  { id: 'endpoints', label: 'Endpoint Graph', icon: <Network size={14}/>, builder: buildEndpointGraph,
    desc: 'API endpoints and their parameter relationships' },
  { id: 'auth', label: 'Authentication Flow', icon: <Shield size={14}/>, builder: buildAuthFlowGraph,
    desc: 'JWT and session token propagation across the application' },
  { id: 'cookies', label: 'Cookie Flow', icon: <GitBranch size={14}/>, builder: buildCookieFlow,
    desc: 'Cookie issuance and consumption across endpoints' },
]

// ── Main Component ─────────────────────────────────────────────────────────────

export default function VisualizationPage() {
  const [activeTab, setActiveTab] = useState('endpoints')
  const currentTab = GRAPH_TABS.find(t => t.id === activeTab)!
  const graphData = useMemo(() => currentTab.builder(), [activeTab])

  const [nodes, setNodes, onNodesChange] = useNodesState(graphData.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(graphData.edges)

  // rebuild on tab switch
  const handleTabChange = useCallback((id: string) => {
    setActiveTab(id)
    const tab = GRAPH_TABS.find(t => t.id === id)!
    const data = tab.builder()
    setNodes(data.nodes)
    setEdges(data.edges)
  }, [setNodes, setEdges])

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-white tracking-tight">Visualization</h1>
        <p className="text-sm text-slate-500 font-mono mt-0.5">{currentTab.desc}</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4">
        {GRAPH_TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => handleTabChange(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
              activeTab === tab.id
                ? 'bg-cyan-500/10 border-cyan-500/40 text-cyan-400'
                : 'bg-[#0D1520] border-[#1E2A3A] text-slate-500 hover:text-slate-300'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Graph */}
      <motion.div
        key={activeTab}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex-1 rounded-xl border border-[#1E2A3A] overflow-hidden"
        style={{ minHeight: 500 }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{ type: 'smoothstep' }}
        >
          <Background color="#1E2A3A" gap={24} />
          <Controls className="!bg-[#0D1520] !border-[#1E2A3A] [&_button]:!bg-[#0D1520] [&_button]:!border-[#1E2A3A] [&_button]:!text-slate-400 [&_button:hover]:!text-cyan-400" />
          <MiniMap
            style={{ backgroundColor: '#0D1520', border: '1px solid #1E2A3A' }}
            maskColor="rgba(5,14,26,0.7)"
            nodeColor="#1E2A3A"
          />
        </ReactFlow>
      </motion.div>

      {/* Legend */}
      <div className="flex items-center gap-6 mt-4 px-2">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <div className="w-3 h-3 rounded border border-cyan-500/40 bg-[#0D1520]" />
          Endpoint
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <div className="w-3 h-3 rounded border border-purple-500/30 bg-[#0D1520]" />
          Parameter
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <div className="w-3 h-3 rounded border-2 border-emerald-500/50 bg-emerald-500/5" />
          Auth Node
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <div className="w-3 h-3 rounded border border-red-500/40 bg-[#0D1520]" />
          High/Critical Risk
        </div>
      </div>
    </div>
  )
}
