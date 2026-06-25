import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';

const validateEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

const validatePassword = (password) => {
  const passwordRegex = /^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{5,}$/;
  return passwordRegex.test(password);
};

const Login = () => {
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [errors, setErrors] = useState({});
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    setErrors(prev => ({
      ...prev,
      [name]: ''
    }));
    toast.dismiss();
  };

  const validateForm = () => {
    const newErrors = {};

    if (!isLoginMode) {
      if (!formData.name.trim()) {
        newErrors.name = 'Name is required';
      }

      if (!formData.email.trim()) {
        newErrors.email = 'Email is required';
      } else if (!validateEmail(formData.email)) {
        newErrors.email = 'Please enter a valid email address';
      }

      if (!formData.password) {
        newErrors.password = 'Password is required';
      } else if (!validatePassword(formData.password)) {
        newErrors.password = 'Password must be at least 5 characters long and contain one uppercase letter, one number, and one special character';
      }

      if (!formData.confirmPassword) {
        newErrors.confirmPassword = 'Please confirm your password';
      } else if (formData.password !== formData.confirmPassword) {
        newErrors.confirmPassword = 'Passwords do not match';
      }
    } else {
      if (!formData.email.trim()) {
        newErrors.email = 'Email is required';
      } else if (!validateEmail(formData.email)) {
        newErrors.email = 'Please enter a valid email address';
      }

      if (!formData.password) {
        newErrors.password = 'Password is required';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    const apiUrl = isLoginMode
      ? 'http://localhost:8000/login'
      : 'http://localhost:8000/register';

    try {
      const payload = isLoginMode
        ? { email: formData.email, password: formData.password }
        : formData;

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (response.ok) {
        if (isLoginMode) {
          if (data.authToken) {
            login({
              status: data.status,
              authToken: data.authToken,
              name: data.name,
              email: data.email,
              role: data.role
            });
            navigate('/');
          }
        } else {
          // Registration successful - show toast and switch to sign-in
          toast.success('Registration successful! Please sign in to continue.', {
            duration: 3000,
            style: {
              background: '#161616',
              color: '#FFFFFF',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: '12px',
              padding: '16px',
              fontSize: '14px',
            },
            iconTheme: {
              primary: '#10B981',
              secondary: '#161616',
            },
          });
          // Switch to login mode
          setIsLoginMode(true);
          // Clear form
          setFormData({
            name: '',
            email: formData.email,
            password: '',
            confirmPassword: ''
          });
        }
      } else {
        toast.error(data.message || data.detail || 'An error occurred', {
          duration: 4000,
          style: {
            background: '#161616',
            color: '#FFFFFF',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '12px',
            padding: '16px',
            fontSize: '14px',
          },
          iconTheme: {
            primary: '#EF4444',
            secondary: '#161616',
          },
        });
      }
    } catch (error) {
      console.error('Auth error:', error);
      toast.error('Network error. Please try again.', {
        duration: 4000,
        style: {
          background: '#161616',
          color: '#FFFFFF',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '12px',
          padding: '16px',
          fontSize: '14px',
        },
        iconTheme: {
          primary: '#EF4444',
          secondary: '#161616',
        },
      });
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center relative overflow-hidden"
      style={{
        backgroundColor: '#0A0A0A',
        fontFamily: 'Satoshi, system-ui, -apple-system, sans-serif'
      }}
    >
      {/* Background Gradients */}
      <div
        className="absolute top-0 left-0 w-96 h-96 rounded-full blur-3xl opacity-80 pointer-events-none"
        style={{
          background: 'radial-gradient(circle, rgba(139,92,246,0.08) 0%, transparent 70%)'
        }}
      />
      <div
        className="absolute bottom-0 right-0 w-96 h-96 rounded-full blur-3xl opacity-80 pointer-events-none"
        style={{
          background: 'radial-gradient(circle, rgba(168,85,247,0.08) 0%, transparent 70%)'
        }}
      />

      {/* Form Container */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-[420px] px-6"
      >
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Header */}
          <div className="text-center mb-8">
            <motion.h2
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: 0.1 }}
              className="text-[24px] font-semibold mb-2"
              style={{ color: '#FFFFFF', fontWeight: 600 }}
            >
              {isLoginMode ? 'Welcome back' : 'Create your account'}
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: 0.15 }}
              className="text-[15px]"
              style={{ color: '#9CA3AF' }}
            >
              {isLoginMode ? 'Sign in to continue your journey' : 'Start building with AI in seconds'}
            </motion.p>
          </div>

          {/* Username Field (Sign Up Only) */}
          {!isLoginMode && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: 0.2 }}
            >
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                className="w-full h-[56px] px-5 rounded-[18px] text-white outline-none transition-all duration-250"
                style={{
                  backgroundColor: '#161616',
                  border: errors.name ? '1px solid #EF4444' : '1px solid rgba(255,255,255,0.05)',
                  fontSize: '15px'
                }}
                placeholder="Username"
                onFocus={(e) => {
                  if (!errors.name) {
                    e.target.style.borderColor = '#8B5CF6';
                    e.target.style.boxShadow = '0 0 0 3px rgba(168,85,247,0.18)';
                  }
                }}
                onBlur={(e) => {
                  if (!errors.name) {
                    e.target.style.borderColor = 'rgba(255,255,255,0.05)';
                    e.target.style.boxShadow = 'none';
                  }
                }}
              />
              {errors.name && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-red-500 text-sm mt-1"
                >
                  {errors.name}
                </motion.p>
              )}
            </motion.div>
          )}

          {/* Email Field */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: isLoginMode ? 0.2 : 0.25 }}
          >
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              className="w-full h-[56px] px-5 rounded-[18px] text-white outline-none transition-all duration-250"
              style={{
                backgroundColor: '#161616',
                border: errors.email ? '1px solid #EF4444' : '1px solid rgba(255,255,255,0.05)',
                fontSize: '15px'
              }}
              placeholder="Email"
              onFocus={(e) => {
                if (!errors.email) {
                  e.target.style.borderColor = '#8B5CF6';
                  e.target.style.boxShadow = '0 0 0 3px rgba(168,85,247,0.18)';
                }
              }}
              onBlur={(e) => {
                if (!errors.email) {
                  e.target.style.borderColor = 'rgba(255,255,255,0.05)';
                  e.target.style.boxShadow = 'none';
                }
              }}
            />
            {errors.email && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-red-500 text-sm mt-1"
              >
                {errors.email}
              </motion.p>
            )}
          </motion.div>

          {/* Password Field */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: isLoginMode ? 0.25 : 0.3 }}
          >
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              className="w-full h-[56px] px-5 rounded-[18px] text-white outline-none transition-all duration-250"
              style={{
                backgroundColor: '#161616',
                border: errors.password ? '1px solid #EF4444' : '1px solid rgba(255,255,255,0.05)',
                fontSize: '15px'
              }}
              placeholder="Password"
              onFocus={(e) => {
                if (!errors.password) {
                  e.target.style.borderColor = '#8B5CF6';
                  e.target.style.boxShadow = '0 0 0 3px rgba(168,85,247,0.18)';
                }
              }}
              onBlur={(e) => {
                if (!errors.password) {
                  e.target.style.borderColor = 'rgba(255,255,255,0.05)';
                  e.target.style.boxShadow = 'none';
                }
              }}
            />
            {errors.password && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-red-500 text-sm mt-1"
              >
                {errors.password}
              </motion.p>
            )}
          </motion.div>

          {/* Confirm Password Field (Sign Up Only) */}
          {!isLoginMode && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: 0.35 }}
            >
              <input
                type="password"
                id="confirmPassword"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                className="w-full h-[56px] px-5 rounded-[18px] text-white outline-none transition-all duration-250"
                style={{
                  backgroundColor: '#161616',
                  border: errors.confirmPassword ? '1px solid #EF4444' : '1px solid rgba(255,255,255,0.05)',
                  fontSize: '15px'
                }}
                placeholder="Confirm Password"
                onFocus={(e) => {
                  if (!errors.confirmPassword) {
                    e.target.style.borderColor = '#8B5CF6';
                    e.target.style.boxShadow = '0 0 0 3px rgba(168,85,247,0.18)';
                  }
                }}
                onBlur={(e) => {
                  if (!errors.confirmPassword) {
                    e.target.style.borderColor = 'rgba(255,255,255,0.05)';
                    e.target.style.boxShadow = 'none';
                  }
                }}
              />
              {errors.confirmPassword && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-red-500 text-sm mt-1"
                >
                  {errors.confirmPassword}
                </motion.p>
              )}
            </motion.div>
          )}

          {/* Submit Button */}
          <motion.button
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: isLoginMode ? 0.3 : 0.4 }}
            type="submit"
            className="w-full h-[60px] rounded-[999px] text-white font-semibold text-[18px] cursor-pointer relative overflow-hidden group"
            style={{
              background: 'linear-gradient(90deg, #8B5CF6 0%, #A855F7 100%)',
              boxShadow: '0 20px 60px rgba(139,92,246,0.35)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'linear-gradient(90deg, #A855F7 0%, #C084FC 100%)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'linear-gradient(90deg, #8B5CF6 0%, #A855F7 100%)';
            }}
          >
            {isLoginMode ? 'Sign In' : 'Create Account'}
          </motion.button>

          {/* Bottom Text */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.25, delay: 0.45 }}
            className="text-center pt-4"
          >
            <span style={{ color: '#6B7280', fontSize: '15px' }}>
              {isLoginMode ? "Don't have an account? " : 'Already have an account? '}
            </span>
            <button
              type="button"
              onClick={() => setIsLoginMode(!isLoginMode)}
              className="font-semibold cursor-pointer transition-colors duration-200 hover:text-purple-400"
              style={{
                color: '#8B5CF6',
                fontSize: '15px'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#C084FC';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = '#8B5CF6';
              }}
            >
              {isLoginMode ? 'Sign Up' : 'Sign In'}
            </button>
          </motion.div>
        </form>
      </motion.div>
    </div>
  );
};

export default Login;