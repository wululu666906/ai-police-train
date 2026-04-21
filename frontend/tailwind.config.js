/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        police: {
          dark: '#1d3557',
          blue: '#457b9d',
          light: '#a8dadc',
          background: '#f2f3f5',
          accent: '#e63946'
        }
      },
      borderRadius: {
        'police': '6px'
      }
    },
  },
  plugins: [],
}
