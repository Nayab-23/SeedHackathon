/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"IBM Plex Mono"', 'Menlo', 'monospace'],
      },
      colors: {
        canvas: '#000000',
        surface: '#0c0c0c',
        raised: '#141414',
        wire: '#1e1e1e',
        dim: '#555555',
        mute: '#888888',
        ghost: '#cccccc',
      },
    },
  },
  plugins: [],
};
