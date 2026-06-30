import { Routes, Route, Navigate } from 'react-router-dom'
import Home from './pages/Home'
import Login from './pages/Login'
import TestPage from './pages/TestPage'
import Results from './pages/Results'
import AdminDashboard from './pages/AdminDashboard'
import ProtectedRoute from './components/ProtectedRoute'
import { useAuth } from './contexts/AuthContext'

function AdminRoute({ children }) {
  const { user } = useAuth()
  if (user?.role !== 'admin' && user?.role !== 'instructor') {
    return <Navigate to="/" replace />
  }
  return children
}

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
        <Route path="/results/:testId" element={
          <ProtectedRoute>
            <Results />
          </ProtectedRoute>
        } />
        <Route path="/admin" element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminDashboard />
            </AdminRoute>
          </ProtectedRoute>
        } />
      </Routes>
    </div>
  )
}

export default App