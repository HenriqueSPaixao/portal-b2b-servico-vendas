/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          // Midnight Green — alinhado ao tema oficial do Portal B2B (Eq.1 Produtos).
          // Visualmente é verde-azulado escuro; vai bem em headers, botões primários,
          // borda de foco e chips de status "ABERTO".
          green: '#075056',
          'green-hover': '#054148',
        },
      },
    },
  },
  plugins: [],
};
