import { useState, useMemo, useCallback } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  ColumnDef,
  SortingState,
  ColumnFiltersState,
} from "@tanstack/react-table";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, Download, Filter, Tag, ChevronUp, ChevronDown,
  ChevronLeft, ChevronRight, Eye, EyeOff, AlertTriangle,
  Shield, Copy, ExternalLink, RefreshCw, X
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

interface Parameter {
  id: string;
  name: string;
  value: string | null;
  param_type: string;
  source: string;
  method: string | null;
  endpoint: string;
  risk_level: string;
  risk_tags: string[];
  is_sensitive: boolean;
  is_hidden: boolean;
  confidence_score: number;
  frequency: number;
  data_type: string | null;
  tags: string[];
  first_seen: string;
  last_seen: string;
}

// ── Risk Badge ─────────────────────────────────────────────────────────────────

const RISK_STYLES: Record<string, string> = {
  info: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  low: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  medium: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  high: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  critical: "bg-red-500/10 text-red-400 border-red-500/20",
};

const TYPE_STYLES: Record<string, string> = {
  url_query: "bg-cyan-500/10 text-cyan-400",
  json_body: "bg-purple-500/10 text-purple-400",
  header_custom: "bg-indigo-500/10 text-indigo-400",
  cookie: "bg-pink-500/10 text-pink-400",
  csrf_token: "bg-red-500/10 text-red-400",
  jwt_claim: "bg-yellow-500/10 text-yellow-400",
  graphql_variable: "bg-teal-500/10 text-teal-400",
  hidden_field: "bg-orange-500/10 text-orange-400",
  api_key: "bg-red-500/10 text-red-400",
};

function RiskBadge({ level }: { level: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${RISK_STYLES[level] || RISK_STYLES.info}`}>
      {level}
    </span>
  );
}

function TypeBadge({ type }: { type: string }) {
  const label = type.replace(/_/g, " ");
  const style = TYPE_STYLES[type] || "bg-slate-500/10 text-slate-400";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono ${style}`}>
      {label}
    </span>
  );
}

// ── Filter Panel ───────────────────────────────────────────────────────────────

const PARAM_TYPES = [
  "url_query", "path", "json_body", "json_nested", "form_urlencoded",
  "header_custom", "header_auth", "cookie", "session", "jwt_claim",
  "hidden_field", "csrf_token", "graphql_variable", "websocket", "api_key",
  "redirect", "pagination", "debug", "feature_flag"
];

const RISK_LEVELS = ["info", "low", "medium", "high", "critical"];

interface FilterPanelProps {
  onFilter: (filters: Record<string, string[]>) => void;
  onClose: () => void;
}

function FilterPanel({ onFilter, onClose }: FilterPanelProps) {
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [selectedRisks, setSelectedRisks] = useState<string[]>([]);
  const [showSensitive, setShowSensitive] = useState<boolean | null>(null);
  const [showHidden, setShowHidden] = useState<boolean | null>(null);

  const toggle = (arr: string[], val: string, set: (v: string[]) => void) => {
    set(arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]);
  };

  const apply = () => {
    onFilter({
      types: selectedTypes,
      risks: selectedRisks,
    });
    onClose();
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className="w-72 bg-[#0D1520] border border-[#1E2A3A] rounded-xl p-4 shadow-2xl"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">Filters</h3>
        <button onClick={onClose} className="text-slate-500 hover:text-white">
          <X size={14} />
        </button>
      </div>

      <div className="space-y-4">
        {/* Risk Level */}
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-widest mb-2">Risk Level</p>
          <div className="flex flex-wrap gap-1.5">
            {RISK_LEVELS.map(r => (
              <button
                key={r}
                onClick={() => toggle(selectedRisks, r, setSelectedRisks)}
                className={`px-2 py-1 rounded text-[11px] font-mono border transition-all ${
                  selectedRisks.includes(r)
                    ? (RISK_STYLES[r] || RISK_STYLES.info) + " border-current"
                    : "border-[#1E2A3A] text-slate-500 hover:text-slate-300"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        {/* Parameter Type */}
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-widest mb-2">Parameter Type</p>
          <div className="max-h-40 overflow-y-auto space-y-1">
            {PARAM_TYPES.map(t => (
              <label key={t} className="flex items-center gap-2 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={selectedTypes.includes(t)}
                  onChange={() => toggle(selectedTypes, t, setSelectedTypes)}
                  className="accent-cyan-500"
                />
                <span className="text-xs font-mono text-slate-400 group-hover:text-slate-200 transition-colors">
                  {t.replace(/_/g, " ")}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Flags */}
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-widest mb-2">Flags</p>
          <div className="space-y-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" className="accent-cyan-500"
                onChange={e => setShowSensitive(e.target.checked ? true : null)}
              />
              <span className="text-xs text-slate-400">Sensitive only</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" className="accent-cyan-500"
                onChange={e => setShowHidden(e.target.checked ? true : null)}
              />
              <span className="text-xs text-slate-400">Hidden fields only</span>
            </label>
          </div>
        </div>
      </div>

      <div className="flex gap-2 mt-4">
        <button
          onClick={() => { setSelectedTypes([]); setSelectedRisks([]); }}
          className="flex-1 py-1.5 text-xs text-slate-500 border border-[#1E2A3A] rounded hover:text-slate-300 transition-colors"
        >
          Clear
        </button>
        <button
          onClick={apply}
          className="flex-1 py-1.5 text-xs bg-cyan-600 hover:bg-cyan-500 text-white rounded transition-colors"
        >
          Apply
        </button>
      </div>
    </motion.div>
  );
}

// ── Main Explorer ──────────────────────────────────────────────────────────────

// Mock data for demo
const MOCK_PARAMS: Parameter[] = Array.from({ length: 200 }, (_, i) => ({
  id: `param-${i}`,
  name: ["user_id", "search", "redirect", "token", "csrf_token", "page", "limit", "sort", "api_key", "debug", "lang", "version", "callback", "format"][i % 14],
  value: ["123", "example query", "https://evil.com", "eyJhbGci...", "abc123", "2", "50", "created_at", "sk-abc123", "true", "en", "v2", "myCallback", "json"][i % 14],
  param_type: ["url_query", "json_body", "redirect", "jwt_claim", "csrf_token", "pagination", "pagination", "sorting", "api_key", "debug", "locale", "version", "url_query", "url_query"][i % 14],
  source: ["url_query", "request_body", "url_query", "header_auth", "form_body", "url_query", "url_query", "url_query", "header_auth", "url_query", "url_query", "url_query", "url_query", "url_query"][i % 14],
  method: ["GET", "POST", "GET", "POST", "POST", "GET", "GET", "GET", "GET", "GET", "GET", "GET", "GET", "GET"][i % 14],
  endpoint: `/api/v${(i % 3) + 1}/endpoint-${Math.floor(i / 3)}`,
  risk_level: ["info", "info", "high", "critical", "medium", "info", "info", "info", "critical", "high", "info", "low", "medium", "info"][i % 14],
  risk_tags: [[], [], ["open-redirect-candidate"], ["api-key-exposure", "sensitive-data"], [], [], [], [], ["api-key-exposure"], ["debug-exposure"], [], [], [], []][i % 14],
  is_sensitive: [false, false, false, true, true, false, false, false, true, false, false, false, false, false][i % 14],
  is_hidden: [false, false, false, false, true, false, false, false, false, false, false, false, false, false][i % 14],
  confidence_score: 0.95,
  frequency: Math.floor(Math.random() * 200) + 1,
  data_type: "string",
  tags: [],
  first_seen: new Date(Date.now() - Math.random() * 86400000 * 30).toISOString(),
  last_seen: new Date().toISOString(),
}));

export default function ParameterExplorer() {
  const [search, setSearch] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
  const [activeFilters, setActiveFilters] = useState<Record<string, string[]>>({});

  const filtered = useMemo(() => {
    let data = MOCK_PARAMS;
    if (search) {
      const s = search.toLowerCase();
      data = data.filter(p =>
        p.name.toLowerCase().includes(s) ||
        (p.value || "").toLowerCase().includes(s) ||
        p.endpoint.toLowerCase().includes(s)
      );
    }
    if (activeFilters.risks?.length) {
      data = data.filter(p => activeFilters.risks.includes(p.risk_level));
    }
    if (activeFilters.types?.length) {
      data = data.filter(p => activeFilters.types.includes(p.param_type));
    }
    return data;
  }, [search, activeFilters]);

  const columns = useMemo<ColumnDef<Parameter>[]>(() => [
    {
      id: "select",
      header: ({ table }) => (
        <input
          type="checkbox"
          className="accent-cyan-500"
          checked={table.getIsAllRowsSelected()}
          onChange={table.getToggleAllRowsSelectedHandler()}
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          className="accent-cyan-500"
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
        />
      ),
      size: 40,
    },
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ getValue, row }) => (
        <div className="flex items-center gap-2">
          {row.original.is_sensitive && <AlertTriangle size={12} className="text-amber-400 flex-shrink-0" />}
          {row.original.is_hidden && <EyeOff size={12} className="text-slate-500 flex-shrink-0" />}
          <span className="font-mono text-sm text-cyan-300 truncate max-w-[180px]">
            {getValue() as string}
          </span>
        </div>
      ),
    },
    {
      accessorKey: "value",
      header: "Value",
      cell: ({ getValue }) => {
        const v = getValue() as string | null;
        if (!v) return <span className="text-slate-600 text-xs">—</span>;
        const truncated = v.length > 30 ? v.slice(0, 30) + "…" : v;
        return (
          <span className="font-mono text-xs text-slate-400 max-w-[160px] truncate block">
            {truncated}
          </span>
        );
      },
    },
    {
      accessorKey: "param_type",
      header: "Type",
      cell: ({ getValue }) => <TypeBadge type={getValue() as string} />,
    },
    {
      accessorKey: "source",
      header: "Source",
      cell: ({ getValue }) => (
        <span className="text-xs font-mono text-slate-500">
          {(getValue() as string).replace(/_/g, " ")}
        </span>
      ),
    },
    {
      accessorKey: "method",
      header: "Method",
      cell: ({ getValue }) => {
        const m = getValue() as string;
        const colors: Record<string, string> = {
          GET: "text-emerald-400", POST: "text-blue-400",
          PUT: "text-amber-400", DELETE: "text-red-400", PATCH: "text-purple-400"
        };
        return (
          <span className={`text-xs font-mono font-bold ${colors[m] || "text-slate-400"}`}>
            {m}
          </span>
        );
      },
    },
    {
      accessorKey: "endpoint",
      header: "Endpoint",
      cell: ({ getValue }) => (
        <span className="font-mono text-xs text-slate-400 truncate max-w-[200px] block">
          {getValue() as string}
        </span>
      ),
    },
    {
      accessorKey: "risk_level",
      header: "Risk",
      cell: ({ getValue }) => <RiskBadge level={getValue() as string} />,
    },
    {
      accessorKey: "frequency",
      header: "Freq.",
      cell: ({ getValue }) => (
        <span className="font-mono text-xs text-slate-400">{getValue() as number}</span>
      ),
    },
    {
      accessorKey: "first_seen",
      header: "First Seen",
      cell: ({ getValue }) => (
        <span className="text-xs text-slate-500 font-mono">
          {new Date(getValue() as string).toLocaleDateString()}
        </span>
      ),
    },
  ], []);

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting, columnFilters },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 50 } },
  });

  const exportCSV = () => {
    const rows = [
      ["Name", "Type", "Source", "Method", "Endpoint", "Risk", "Sensitive", "Hidden", "Frequency", "First Seen"],
      ...filtered.map(p => [
        p.name, p.param_type, p.source, p.method || "", p.endpoint,
        p.risk_level, p.is_sensitive, p.is_hidden, p.frequency, p.first_seen
      ])
    ];
    const csv = rows.map(r => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "parameters.csv";
    a.click();
  };

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Parameter Explorer</h1>
          <p className="text-sm text-slate-500 font-mono mt-0.5">
            {filtered.length.toLocaleString()} parameters found
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={exportCSV}
            className="flex items-center gap-2 px-3 py-2 text-xs bg-[#0D1520] border border-[#1E2A3A] rounded-lg text-slate-400 hover:text-cyan-400 hover:border-cyan-500/40 transition-all"
          >
            <Download size={13} />
            Export CSV
          </button>
          <button className="flex items-center gap-2 px-3 py-2 text-xs bg-[#0D1520] border border-[#1E2A3A] rounded-lg text-slate-400 hover:text-cyan-400 hover:border-cyan-500/40 transition-all">
            <Download size={13} />
            Export JSON
          </button>
        </div>
      </div>

      {/* Search + Filters Bar */}
      <div className="flex items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={15} />
          <input
            type="text"
            placeholder="Search parameters, values, endpoints..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-[#0D1520] border border-[#1E2A3A] rounded-lg py-2 pl-9 pr-4 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/60 transition-colors font-mono"
          />
        </div>
        <div className="relative">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-3 py-2 text-xs border rounded-lg transition-all ${
              showFilters
                ? "bg-cyan-500/10 border-cyan-500/40 text-cyan-400"
                : "bg-[#0D1520] border-[#1E2A3A] text-slate-400 hover:text-cyan-400"
            }`}
          >
            <Filter size={13} />
            Filters
            {(activeFilters.risks?.length || activeFilters.types?.length) ? (
              <span className="w-4 h-4 rounded-full bg-cyan-500 text-white text-[10px] flex items-center justify-center">
                {(activeFilters.risks?.length || 0) + (activeFilters.types?.length || 0)}
              </span>
            ) : null}
          </button>

          <AnimatePresence>
            {showFilters && (
              <div className="absolute top-full right-0 mt-2 z-50">
                <FilterPanel
                  onFilter={setActiveFilters}
                  onClose={() => setShowFilters(false)}
                />
              </div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-[#1E2A3A] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              {table.getHeaderGroups().map(hg => (
                <tr key={hg.id} className="border-b border-[#1E2A3A] bg-[#07101C]">
                  {hg.headers.map(header => (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className={`px-3 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-widest whitespace-nowrap ${
                        header.column.getCanSort() ? "cursor-pointer hover:text-slate-300 select-none" : ""
                      }`}
                    >
                      <div className="flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === "asc" && <ChevronUp size={12} />}
                        {header.column.getIsSorted() === "desc" && <ChevronDown size={12} />}
                      </div>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row, i) => (
                <motion.tr
                  key={row.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.005 }}
                  className={`border-b border-[#1E2A3A]/50 hover:bg-[#0D1520] transition-colors ${
                    row.original.is_sensitive ? "bg-amber-500/3" : ""
                  }`}
                >
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} className="px-3 py-2.5">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-[#1E2A3A] bg-[#07101C]">
          <span className="text-xs text-slate-500 font-mono">
            {table.getRowModel().rows.length} of {filtered.length} rows
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              className="p-1 rounded text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-xs font-mono text-slate-400">
              Page {table.getState().pagination.pageIndex + 1} / {table.getPageCount()}
            </span>
            <button
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              className="p-1 rounded text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
