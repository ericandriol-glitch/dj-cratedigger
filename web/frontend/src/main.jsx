import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import AppV2 from './AppV2.jsx'

// Switch via URL param: /?v=2
const params = new URLSearchParams(window.location.search);
const version = params.get('v');
const RootApp = version === '2' ? AppV2 : App;

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <RootApp />
  </StrictMode>,
)
