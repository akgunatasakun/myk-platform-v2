import '@/styles/app.css'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import PwaUpdatePrompt from '@/components/pwa/PwaUpdatePrompt'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
    <PwaUpdatePrompt />
  </React.StrictMode>
)
