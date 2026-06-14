import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity, Globe, Hash, Eye, EyeOff, Wifi,
  Zap, TrendingUp, Shield, AlertTriangle, RefreshCw
} from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from "recharts";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

interface DashboardStats {
  total_endpoints: number;
  total_parameters: number;
  unique_parameters: number;
  hidden_parameters: number;
  apis_discovered: number;
  websockets_found: number;
  active_scans: number;
  total_scans: number;
  sensitive_parameters: number;
  risk_distribution: Record<string, number>;
  param_type_distribution: Record<string, number>;
  requests_over_time: Array<{ time: string; requests: number; params: number }>;
  top_endpoints: Array<{ endpoint: string; param_count: number }>;
}

// ── Stat Card ──────────────────────────────────────────────────────────────────

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: number;
  color: string;
  delay?: number;
}

function StatCard({ title, value, icon, trend, color, delay = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4, ease: "easeOut" }}
      className="relative overflow-hidden rounded-xl border border-[#1E2A3A] bg-[#0D1520] p-5 group hover:border-cyan-500/40 transition-colors duration-300"
    >
      {/* Glow effect */}
      <div
        className="absolute -top-10 -right-10 w-32 h-32 rounded-full opacity-10 blur-2xl group-hover:opacity-20 transition-opacity"
        style={{ backgroundColor: color }}
      />

      <div className="relative z-10">
        <div className="flex items-start justify-between mb-3">
          <div
            className="p-2 rounded-lg"
            style={{ backgroundColor: `${color}20`, color }}
          >
            {icon}
          </div>
          {trend !== undefined && (
            <span className={`text-xs font-mono ${trend >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {trend >= 0 ? "▲" : "▼"} {Math.abs(trend)}%
            </span>
          )}
        </div>
        <div className="mt-2">
          <p className="text-3xl font-bold font-mono text-white tracking-tight">
            {typeof value === "number" ? value.toLocaleString() : value}
          </p>
          <p className="text-xs text-slate-500 mt-1 uppercase tracking-widest font-medium">
            {title}
          </p>
        </div>
      </div>
    </motion.div>
  );
}

// ── Risk Badge ─────────────────────────────────────────────────────────────────

const RISK_COLORS: Record<string, string> = {
  info: "#60a5fa",
  low: "#34d399",
  medium: "#fbbf24",
  high: "#f97316",
  critical: "#ef4444",
};

// ── Active Scan Row ────────────────────────────────────────────────────────────

interface ActiveScanProps {
  scan: {
    id: string;
    name: string;
    target: string;
    progress: number;
    parameters: number;
    status: string;
  };
}

function ActiveScanRow({ scan }: ActiveScanProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex items-center gap-4 py-3 border-b border-[#1E2A3A] last:border-0"
    >
      <div className="flex-shrink-0">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
          className="w-8 h-8 rounded-full border-2 border-cyan-500 border-t-transparent"
        />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white truncate">{scan.name}</p>
        <p className="text-xs text-slate-500 truncate font-mono">{scan.target}</p>
      </div>
      <div className="flex-1 max-w-[140px]">
        <div className="flex justify-between text-xs text-slate-400 mb-1">
          <span>{scan.progress}%</span>
          <span className="font-mono text-cyan-400">{scan.parameters.toLocaleString()} params</span>
        </div>
        <div className="h-1.5 bg-[#1E2A3A] rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${scan.progress}%` }}
            transition={{ duration: 1 }}
          />
        </div>
      </div>
    </motion.div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [refreshKey, setRefreshKey] = useState(0);

  const { data: stats, isLoading } = useQuery<DashboardStats>({
    queryKey: ["dashboard-stats", refreshKey],
    queryFn: () => api.get("/dashboard/stats").then(r => r.data),
    refetchInterval: 10_000,
  });

  const mockStats: DashboardStats = {
    total_endpoints: 2847,
    total_parameters: 48_392,
    unique_parameters: 3_714,
    hidden_parameters: 219,
    apis_discovered: 47,
    websockets_found: 8,
    active_scans: 2,
    total_scans: 31,
    sensitive_parameters: 183,
    risk_distribution: { info: 38291, low: 6843, medium: 2204, high: 891, critical: 163 },
    param_type_distribution: {
      url_query: 18432, json_body: 12891, header_custom: 7293,
      cookie: 3821, form_urlencoded: 2941, graphql_variable: 1892,
      hidden_field: 1122
    },
    requests_over_time: Array.from({ length: 24 }, (_, i) => ({
      time: `${i}:00`,
      requests: Math.floor(Math.random() * 4000) + 500,
      params: Math.floor(Math.random() * 2000) + 100,
    })),
    top_endpoints: [
      { endpoint: "/api/v1/users", param_count: 47 },
      { endpoint: "/api/v1/products/search", param_count: 38 },
      { endpoint: "/graphql", param_count: 31 },
      { endpoint: "/api/v1/orders", param_count: 28 },
      { endpoint: "/api/v1/auth/login", param_count: 12 },
    ],
  };

  const data = stats || mockStats;

  const PIE_COLORS = Object.values(RISK_COLORS);
  const riskData = Object.entries(data.risk_distribution).map(([k, v]) => ({
    name: k.charAt(0).toUpperCase() + k.slice(1),
    value: v,
    color: RISK_COLORS[k],
  }));

  const paramTypeData = Object.entries(data.param_type_distribution)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([k, v]) => ({
      name: k.replace(/_/g, " "),
      count: v,
    }));

  const mockActiveScans = [
    { id: "1", name: "Prod API Audit Q1", target: "api.example.com", progress: 67, parameters: 8432, status: "running" },
    { id: "2", name: "Staging Deep Scan", target: "staging.example.com", progress: 23, parameters: 1841, status: "running" },
  ];

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            Attack Surface Dashboard
          </h1>
          <p className="text-sm text-slate-500 mt-0.5 font-mono">
            Real-time parameter discovery & API inventory
          </p>
        </div>
        <button
          onClick={() => setRefreshKey(k => k + 1)}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-[#0D1520] border border-[#1E2A3A] rounded-lg text-slate-400 hover:text-cyan-400 hover:border-cyan-500/40 transition-all"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* Stat Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="Total Endpoints" value={data.total_endpoints} icon={<Globe size={18} />} color="#06b6d4" trend={12} delay={0} />
        <StatCard title="Total Parameters" value={data.total_parameters} icon={<Hash size={18} />} color="#8b5cf6" trend={8} delay={0.05} />
        <StatCard title="Unique Parameters" value={data.unique_parameters} icon={<Zap size={18} />} color="#3b82f6" delay={0.1} />
        <StatCard title="Hidden Fields" value={data.hidden_parameters} icon={<EyeOff size={18} />} color="#f59e0b" trend={-3} delay={0.15} />
        <StatCard title="APIs Discovered" value={data.apis_discovered} icon={<Activity size={18} />} color="#10b981" delay={0.2} />
        <StatCard title="WebSockets Found" value={data.websockets_found} icon={<Wifi size={18} />} color="#ec4899" delay={0.25} />
        <StatCard title="Sensitive Params" value={data.sensitive_parameters} icon={<AlertTriangle size={18} />} color="#ef4444" delay={0.3} />
        <StatCard title="Active Scans" value={data.active_scans} icon={<Shield size={18} />} color="#22d3ee" delay={0.35} />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Requests over time */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="lg:col-span-2 rounded-xl border border-[#1E2A3A] bg-[#0D1520] p-5"
        >
          <h3 className="text-sm font-semibold text-slate-300 mb-4 uppercase tracking-widest">
            Requests & Parameters — 24h
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={data.requests_over_time}>
              <defs>
                <linearGradient id="requests" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="params" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E2A3A" />
              <XAxis dataKey="time" tick={{ fill: "#475569", fontSize: 11 }} />
              <YAxis tick={{ fill: "#475569", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#0D1520", border: "1px solid #1E2A3A", borderRadius: 8 }}
                labelStyle={{ color: "#94a3b8" }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
              <Area type="monotone" dataKey="requests" stroke="#06b6d4" fill="url(#requests)" strokeWidth={2} name="Requests" />
              <Area type="monotone" dataKey="params" stroke="#8b5cf6" fill="url(#params)" strokeWidth={2} name="Parameters" />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Risk Distribution */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
          className="rounded-xl border border-[#1E2A3A] bg-[#0D1520] p-5"
        >
          <h3 className="text-sm font-semibold text-slate-300 mb-4 uppercase tracking-widest">
            Risk Distribution
          </h3>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie
                data={riskData}
                cx="50%"
                cy="50%"
                innerRadius={45}
                outerRadius={70}
                paddingAngle={3}
                dataKey="value"
              >
                {riskData.map((entry, index) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: "#0D1520", border: "1px solid #1E2A3A", borderRadius: 8 }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-2 space-y-1.5">
            {riskData.map(item => (
              <div key={item.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-slate-400">{item.name}</span>
                </div>
                <span className="font-mono text-slate-300">{item.value.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Parameter Types */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="lg:col-span-2 rounded-xl border border-[#1E2A3A] bg-[#0D1520] p-5"
        >
          <h3 className="text-sm font-semibold text-slate-300 mb-4 uppercase tracking-widest">
            Parameter Types
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={paramTypeData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1E2A3A" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#475569", fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} width={130} />
              <Tooltip
                contentStyle={{ background: "#0D1520", border: "1px solid #1E2A3A", borderRadius: 8 }}
              />
              <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} name="Count">
                {paramTypeData.map((_, i) => (
                  <Cell key={i} fill={`hsl(${260 + i * 10}, 70%, 60%)`} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Active Scans */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55 }}
          className="rounded-xl border border-[#1E2A3A] bg-[#0D1520] p-5"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-widest">
              Active Scans
            </h3>
            <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              LIVE
            </span>
          </div>
          {mockActiveScans.length === 0 ? (
            <p className="text-sm text-slate-600 text-center py-8">No active scans</p>
          ) : (
            <div>
              {mockActiveScans.map(scan => (
                <ActiveScanRow key={scan.id} scan={scan} />
              ))}
            </div>
          )}
          {/* Top Endpoints */}
          <div className="mt-4 pt-4 border-t border-[#1E2A3A]">
            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">
              Top Endpoints by Params
            </h4>
            {data.top_endpoints.map((ep, i) => (
              <div key={ep.endpoint} className="flex items-center justify-between py-1.5">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-xs font-mono text-slate-600 w-4">{i + 1}</span>
                  <span className="text-xs font-mono text-slate-400 truncate">{ep.endpoint}</span>
                </div>
                <span className="text-xs font-mono text-cyan-400 flex-shrink-0 ml-2">
                  {ep.param_count}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
