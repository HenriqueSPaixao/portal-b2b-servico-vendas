/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          green: '#4cc465',
          'green-hover': '#3fa854',
        },
      },
    },
  },
  plugins: [],
};
