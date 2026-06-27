import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Login from './pages/Login'
import TestPage from './pages/TestPage'
import ProtectedRoute from './components/ProtectedRoute'

function App() {
  return (
    <div className="min-h-screen bg-primary">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={
          <ProtectedRoute>
            <Home />
          </ProtectedRoute>
        } />
        <Route path="/test/:testId" element={
          <ProtectedRoute>
            <TestPage />
          </ProtectedRoute>
        } />
      </Routes>
    </div>
  )
}

export default App