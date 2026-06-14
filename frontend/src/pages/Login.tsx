import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Zap, Eye, EyeOff, AlertCircle } from 'lucide-react'
import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore(s => s.login)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const form = new URLSearchParams()
      form.append('username', email)
      form.append('password', password)
      const res = await axios.post('/api/v1/auth/token', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      const { access_token, refresh_token } = res.data
      // Decode user info from token (just parse payload for display)
      const payload = JSON.parse(atob(access_token.split('.')[1]))
      login(access_token, refresh_token, {
        id: payload.sub,
        email: payload.email,
        username: payload.email?.split('@')[0] ?? 'user',
        role: payload.role ?? 'analyst',
      })
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Login failed. Check credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#050E1A] flex items-center justify-center p-4">
      {/* Background grid */}
      <div
        className="absolute inset-0 opacity-20"
        style={{
          backgroundImage: 'linear-gradient(rgba(6,182,212,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.05) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative w-full max-w-sm"
      >
        {/* Glow */}
        <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500/20 to-purple-600/20 rounded-2xl blur-xl" />

        <div className="relative bg-[#0D1520] border border-[#1E2A3A] rounded-2xl p-8">
          {/* Logo */}
          <div className="flex justify-center mb-6">
            <div className="w-14 h-14 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
              <Zap size={28} className="text-cyan-400" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white text-center tracking-tight">ParamX Hunter</h1>
          <p className="text-slate-500 text-sm text-center mt-1 mb-8 font-mono">Attack Surface Mapping Platform</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 uppercase tracking-widest mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="analyst@example.com"
                className="w-full bg-[#07101C] border border-[#1E2A3A] rounded-lg py-2.5 px-3 text-sm text-slate-200 placeholder:text-slate-700 focus:outline-none focus:border-cyan-500/60 font-mono transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 uppercase tracking-widest mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className="w-full bg-[#07101C] border border-[#1E2A3A] rounded-lg py-2.5 pl-3 pr-10 text-sm text-slate-200 placeholder:text-slate-700 focus:outline-none focus:border-cyan-500/60 font-mono transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-300"
                >
                  {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="flex items-center gap-2 text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2"
              >
                <AlertCircle size={12} className="flex-shrink-0" />
                {error}
              </motion.div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors mt-2"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Authenticating...
                </span>
              ) : 'Sign In'}
            </button>
          </form>

          <p className="text-center text-xs text-slate-700 mt-6 font-mono">
            Authorized security testing only
          </p>
        </div>
      </motion.div>
    </div>
  )
}
