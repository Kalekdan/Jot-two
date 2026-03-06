import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import Chat from './pages/Chat.jsx'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="nav">
          <div className="nav-brand">
            <span className="nav-logo">⚡</span>
            <span className="nav-title">Jot-two Manager</span>
          </div>
          <div className="nav-links">
            <NavLink
              to="/"
              end
              className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/chat"
              className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}
            >
              Chat
            </NavLink>
          </div>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chat" element={<Chat />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
