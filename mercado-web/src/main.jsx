import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import { bootstrapJwt } from './lib/jwt-handshake.js';
import { applyInitialTheme } from './lib/theme.js';
import './index.css';

bootstrapJwt();
applyInitialTheme();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
