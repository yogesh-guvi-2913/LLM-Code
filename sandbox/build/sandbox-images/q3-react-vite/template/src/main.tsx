// main.tsx — fixed entry point. Mounts <App/>. Candidates implement App.tsx.
// (This file is part of the reset-on-claim src tree but is not what's graded.)
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
