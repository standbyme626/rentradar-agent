/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        canvas: '#f6f3ec',
        paper: '#fffdf9',
        paper2: '#fbf8f1',
        sand: '#efe9de',
        ink: '#1c1b19',
        muted: '#6f6a62',
        faint: '#9a948a',
        line: '#e6e0d6',
        line2: '#d8d0c2',
        forest: { DEFAULT: '#1f5d4a', dark: '#174638', soft: '#e6efe9' },
        coral: { DEFAULT: '#c25934', soft: '#f8e9e2' },
        amber: { DEFAULT: '#a8741a', soft: '#f8efdc' },
        sidebar: { DEFAULT: '#12211b', 2: '#1a2f26', line: '#274137' },
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'PingFang SC',
          'Hiragino Sans GB',
          'Microsoft YaHei',
          'sans-serif',
        ],
      },
      boxShadow: {
        card: '0 1px 3px rgba(28,27,25,.04), 0 12px 34px rgba(28,27,25,.05)',
        lift: '0 18px 42px rgba(28,27,25,.11)',
      },
    },
  },
  plugins: [],
}
