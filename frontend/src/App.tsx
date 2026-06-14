import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from '@/components/layout/AppLayout'
import Dashboard from '@/pages/Dashboard'
import ParameterExplorer from '@/pages/ParameterExplorer'
import EndpointsPage from '@/pages/Endpoints'
import ScansPage from '@/pages/Scans'
import VisualizationPage from '@/pages/Visualization'
import ReportsPage from '@/pages/Reports'
import LoginPage from '@/pages/Login'
import { useAuthStore } from '@/stores/authStore'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore(s => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="parameters" element={<ParameterExplorer />} />
          <Route path="endpoints" element={<EndpointsPage />} />
          <Route path="scans" element={<ScansPage />} />
          <Route path="visualization" element={<VisualizationPage />} />
          <Route path="reports" element={<ReportsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
