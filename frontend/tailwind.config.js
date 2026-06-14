/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Cyber dark palette
        cyber: {
          bg:       '#050E1A',
          card:     '#0D1520',
          surface:  '#0A1526',
          border:   '#1E2A3A',
          muted:    '#334155',
          cyan:     '#06B6D4',
          blue:     '#3B82F6',
          purple:   '#8B5CF6',
          green:    '#10B981',
          amber:    '#F59E0B',
          orange:   '#F97316',
          red:      '#EF4444',
          pink:     '#EC4899',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan-line': 'scanLine 4s linear infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        scanLine: {
          '0%': { top: '0%' },
          '100%': { top: '100%' },
        },
        glow: {
          from: { boxShadow: '0 0 5px #06b6d4, 0 0 10px #06b6d4' },
          to:   { boxShadow: '0 0 10px #06b6d4, 0 0 30px #06b6d4, 0 0 50px #06b6d480' },
        },
      },
      backgroundImage: {
        'grid-cyber': "linear-gradient(rgba(6,182,212,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.03) 1px, transparent 1px)",
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      },
      backgroundSize: {
        'grid': '32px 32px',
      },
    },
  },
  plugins: [],
}
