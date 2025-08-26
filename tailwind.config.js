/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './*/templates/**/*.html',  // Catch-all for Django app templates
    './static/js/**/*.js',
    './**/*.py',  // Scan Python files for dynamic classes
  ],
  theme: {
    extend: {
      fontFamily: {
        'heading': ['Montserrat', 'sans-serif'],
        'sans': ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        'brand': {
          'black': '#000000',
          'white': '#ffffff', 
          'silver': '#c0c0c0',
          'green': '#10b981',
          'red': '#ef4444',
        }
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}

