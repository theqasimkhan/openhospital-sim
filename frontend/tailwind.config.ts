import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#F8FAFC',
          1: '#FFFFFF',
          2: '#F1F5F9',
          3: '#E2E8F0',
          4: '#FFFFFF',
          border: '#CBD5E1',
        },
        brand: {
          cyan: '#06B6D4',
          blue: '#2563EB',
          teal: '#14B8A6',
          navy: '#1E3A8A',
        },
        status: {
          ok: '#10B981',
          warn: '#F59E0B',
          critical: '#EF4444',
          info: '#3B82F6',
        },
        text: {
          primary: '#0F172A',
          secondary: '#475569',
          muted: '#64748B',
          accent: '#2563EB',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      backgroundImage: {
        'grid-pattern': "url(\"data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' width='32' height='32' fill='none' stroke='rgb(203 213 225 / 0.6)'%3e%3cpath d='M0 .5H31.5V32'/%3e%3c/svg%3e\")",
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
export default config
