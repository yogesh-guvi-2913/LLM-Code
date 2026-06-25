import { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export const useAuth = () => {
  return useContext(AuthContext);
};

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const status = localStorage.getItem('status');
    const authToken = localStorage.getItem('authToken');
    const name = localStorage.getItem('name');
    const email = localStorage.getItem('email');
    const role = localStorage.getItem('role');

    if (status === 'success' && authToken) {
      setIsAuthenticated(true);
      setUser({ authToken, name, email, role });
    }
    setLoading(false);
  }, []);

  const login = ({ status, authToken, name, email, role }) => {
    localStorage.setItem('status', status);
    localStorage.setItem('authToken', authToken);
    localStorage.setItem('name', name);
    localStorage.setItem('email', email);
    localStorage.setItem('role', role);
    setIsAuthenticated(true);
    setUser({ authToken, name, email, role });
  };

  const logout = () => {
    localStorage.removeItem('status');
    localStorage.removeItem('authToken');
    localStorage.removeItem('name');
    localStorage.removeItem('email');
    localStorage.removeItem('role');
    setIsAuthenticated(false);
    setUser(null);
  };

  const value = {
    isAuthenticated,
    user,
    login,
    logout,
    loading
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};