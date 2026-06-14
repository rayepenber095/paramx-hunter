import { create } from 'zustand'

interface ScanProgress {
  scanId: string
  name: string
  target: string
  percent: number
  totalRequests: number
  totalParams: number
  queueSize: number
  status: 'running' | 'paused' | 'completed' | 'failed'
}

interface ScanStore {
  activeScans: Record<string, ScanProgress>
  updateScan: (scanId: string, data: Partial<ScanProgress>) => void
  removeScan: (scanId: string) => void
  recentParams: Array<{ name: string; type: string; endpoint: string; risk: string; ts: number }>
  addRecentParam: (p: ScanStore['recentParams'][0]) => void
}

export const useScanStore = create<ScanStore>(set => ({
  activeScans: {},
  updateScan: (scanId, data) =>
    set(state => ({
      activeScans: {
        ...state.activeScans,
        [scanId]: { ...(state.activeScans[scanId] ?? {}), ...data, scanId } as ScanProgress,
      },
    })),
  removeScan: scanId =>
    set(state => {
      const { [scanId]: _, ...rest } = state.activeScans
      return { activeScans: rest }
    }),
  recentParams: [],
  addRecentParam: p =>
    set(state => ({
      recentParams: [p, ...state.recentParams].slice(0, 100),
    })),
}))
