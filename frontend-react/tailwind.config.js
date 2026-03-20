/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Core terminal palette
        void: '#050505',
        background: '#0a0a0a',
        surface: {
          DEFAULT: '#0f0f0f',
          raised: '#141414',
          hover: '#1a1a1a',
        },
        border: {
          DEFAULT: '#1e1e1e',
          subtle: '#161616',
          strong: '#2a2a2a',
        },
        // Text hierarchy
        'text-primary': '#e8e6e3',
        'text-secondary': '#6b6b6b',
        'text-muted': '#3a3a3a',
        // Signal colors — terminal-inspired
        signal: {
          green: '#00ff87',
          amber: '#ffb700',
          red: '#ff3b30',
          blue: '#00d4ff',
          dim: '#1a3a1a',
        },
        // Grade system
        grade: {
          a: '#00ff87',
          b: '#00d4ff',
          c: '#ffb700',
          d: '#4a4a4a',
        },
        // Accent
        accent: {
          DEFAULT: '#c8ff00',
          hover: '#d4ff33',
          dim: '#1a2200',
        },
      },
      fontFamily: {
        mono: ['"DM Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
        sans: ['"Plus Jakarta Sans"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
        'display': ['3.5rem', { lineHeight: '1', letterSpacing: '-0.03em', fontWeight: '400' }],
        'headline': ['1.75rem', { lineHeight: '1.15', letterSpacing: '-0.02em' }],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      backgroundImage: {
        'scanline': 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.008) 2px, rgba(255,255,255,0.008) 4px)',
        'grid-pattern': 'linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)',
        'glow-green': 'radial-gradient(ellipse at center, rgba(0,255,135,0.08) 0%, transparent 70%)',
        'glow-amber': 'radial-gradient(ellipse at center, rgba(255,183,0,0.06) 0%, transparent 70%)',
      },
      backgroundSize: {
        'grid': '24px 24px',
      },
      boxShadow: {
        'glow-sm': '0 0 10px rgba(0,255,135,0.1)',
        'glow-md': '0 0 20px rgba(0,255,135,0.15)',
        'glow-amber': '0 0 20px rgba(255,183,0,0.12)',
        'inner-glow': 'inset 0 1px 0 rgba(255,255,255,0.03)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-down': 'slideDown 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'terminal-blink': 'terminalBlink 1.2s step-end infinite',
        'scan': 'scan 8s linear infinite',
        'number-tick': 'numberTick 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        terminalBlink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        numberTick: {
          '0%': { transform: 'translateY(-100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
