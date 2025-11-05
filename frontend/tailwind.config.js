/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#000000',
          light: '#333333',
        },
        secondary: {
          DEFAULT: '#FFFFFF',
          dark: '#F5F5F5',
        },
        accent: {
          DEFAULT: '#666666',
          light: '#999999',
        },
      },
    },
  },
  plugins: [],
}
