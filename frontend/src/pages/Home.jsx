import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { motion, AnimatePresence } from 'framer-motion';
import { LayoutDashboard, FlaskConical, MessageSquare, BarChart, LogOut, User, ShoppingBag, ArrowRight, TrendingUp, Clock, CheckCircle, Zap, Bell, Search, Plus, MoreHorizontal, Sparkles } from 'lucide-react';
import sidebarLogo from '../assets/sidebar-logo.png';
import LogoutModal from '../components/LogoutModal';

const Home = () => {
  const { user, logout: authLogout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('dashboard');
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const sidebarItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'tests', label: 'Tests', icon: FlaskConical },
    { id: 'feedback', label: 'Feedback', icon: MessageSquare },
    { id: 'reports', label: 'Reports', icon: BarChart }
  ];

  const stats = [
    { label: 'Total Tests', value: '24', change: '+12%', trend: 'up', icon: FlaskConical },
    { label: 'Passed', value: '18', change: '+8%', trend: 'up', icon: CheckCircle },
    { label: 'Failed', value: '3', change: '-2%', trend: 'down', icon: TrendingUp },
    { label: 'Pending', value: '3', change: '0%', trend: 'neutral', icon: Clock }
  ];

  const testCard = {
    id: 1,
    title: 'Ecommerce Website',
    description: 'Comprehensive testing for AI models in ecommerce scenarios including product recommendations, search, and checkout flows.',
    status: 'Available',
    difficulty: 'Intermediate',
    duration: '15 min',
    icon: ShoppingBag,
    category: 'Production'
  };

  const handleLogout = () => {
    setShowLogoutModal(true);
  };

  const confirmLogout = async () => {
    setIsLoggingOut(true);

    try {
      const response = await fetch('http://localhost:8000/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          authToken: user?.authToken
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        // Clear auth context and redirect
        authLogout();
        navigate('/login');
      } else {
        console.error('Logout failed:', data.message || 'Unknown error');
        // Still logout locally even if backend fails
        authLogout();
        navigate('/login');
      }
    } catch (error) {
      console.error('Logout error:', error);
      // Still logout locally even if backend fails
      authLogout();
      navigate('/login');
    } finally {
      setIsLoggingOut(false);
      setShowLogoutModal(false);
    }
  };

  const cancelLogout = () => {
    setShowLogoutModal(false);
  };

  return (
    <div
      className="flex min-h-screen"
      style={{
        backgroundColor: '#0A0A0A',
        fontFamily: 'Satoshi, system-ui, -apple-system, sans-serif'
      }}
    >
      {/* Sidebar - Fixed position */}
      <aside className="fixed left-0 top-0 h-screen w-72 flex flex-col z-50" style={{ backgroundColor: '#0D0D0D', borderRight: '1px solid rgba(255,255,255,0.06)' }}>
        {/* Logo Section */}
        <div className="p-6 border-b" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
          <motion.div
            initial={{ scale: 0.95 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.4, type: 'spring' }}
            className="group cursor-pointer"
          >
            <img
              src={sidebarLogo}
              alt="PromptAI Logo"
              className="w-full h-auto object-contain transition-transform duration-300 group-hover:scale-105"
            />
          </motion.div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-8 space-y-2">
          {sidebarItems.map((item, index) => (
            <motion.button
              key={item.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3, delay: 0.05 * index }}
              onClick={() => setActiveTab(item.id)}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 relative overflow-hidden group"
              style={{
                backgroundColor: activeTab === item.id ? 'rgba(139,92,246,0.12)' : 'transparent'
              }}
            >
              {activeTab === item.id && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl"
                  style={{ background: 'linear-gradient(180deg, #8B5CF6 0%, #A855F7 100%)' }}
                />
              )}
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300"
                style={{
                  backgroundColor: activeTab === item.id ? 'rgba(139,92,246,0.25)' : 'rgba(255,255,255,0.04)',
                  color: activeTab === item.id ? '#C4B5FD' : '#9CA3AF'
                }}
              >
                <item.icon size={20} strokeWidth={2} />
              </div>
              <span
                className="text-base font-medium transition-colors duration-200"
                style={{
                  color: activeTab === item.id ? '#FFFFFF' : '#9CA3AF',
                  fontWeight: activeTab === item.id ? 600 : 500
                }}
              >
                {item.label}
              </span>
            </motion.button>
          ))}
        </nav>

        {/* User Profile Section */}
        <div className="p-4 border-t" style={{ borderColor: 'rgba(255,255,255,0.06)', backgroundColor: 'rgba(0,0,0,0.2)' }}>
          <div className="flex items-center gap-3 p-3 rounded-xl" style={{ backgroundColor: 'rgba(255,255,255,0.02)' }}>
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold text-sm"
              style={{
                background: 'linear-gradient(135deg, #8B5CF6 0%, #A855F7 100%)',
                boxShadow: '0 0 16px rgba(139,92,246,0.3)'
              }}
            >
              {user?.name?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate" style={{ color: '#FFFFFF', fontWeight: 600 }}>
                {user?.name || 'User'}
              </p>
              <p className="text-xs truncate" style={{ color: '#6B7280' }}>
                {user?.email || ''}
              </p>
            </div>
            <button
              onClick={handleLogout}
              className="p-2 rounded-lg transition-colors"
              style={{ color: '#6B7280' }}
              onMouseEnter={(e) => e.currentTarget.style.color = '#EF4444'}
              onMouseLeave={(e) => e.currentTarget.style.color = '#6B7280'}
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content - with margin to account for fixed sidebar */}
      <div className="flex-1 flex flex-col overflow-hidden ml-72">
        {/* Header */}
        <header
          className="h-20 px-8 flex items-center justify-between relative"
          style={{
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            backgroundColor: 'rgba(10,10,10,0.8)',
            backdropFilter: 'blur(20px)'
          }}
        >
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-2xl font-bold" style={{ color: '#FFFFFF', fontWeight: 600, letterSpacing: '-0.02em' }}>
                {sidebarItems.find(item => item.id === activeTab)?.label || 'Dashboard'}
              </h2>
              <p className="text-sm" style={{ color: '#6B7280' }}>
                Welcome back, {user?.name?.split(' ')[0] || 'User'} 👋
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              className="p-2.5 rounded-xl transition-all duration-200"
              style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#6B7280' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)';
                e.currentTarget.style.color = '#FFFFFF';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)';
                e.currentTarget.style.color = '#6B7280';
              }}
            >
              <Search size={18} />
            </button>
            <button
              className="p-2.5 rounded-xl transition-all duration-200 relative"
              style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#6B7280' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)';
                e.currentTarget.style.color = '#FFFFFF';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)';
                e.currentTarget.style.color = '#6B7280';
              }}
            >
              <Bell size={18} />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full" style={{ backgroundColor: '#8B5CF6' }} />
            </button>
            <div
              className="flex items-center gap-2.5 px-4 py-2 rounded-xl"
              style={{
                backgroundColor: 'rgba(16,185,129,0.1)',
                border: '1px solid rgba(16,185,129,0.2)'
              }}
            >
              <div className="relative">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#10B981' }} />
                <div className="absolute inset-0 w-2 h-2 rounded-full animate-ping" style={{ backgroundColor: '#10B981', opacity: 0.5 }} />
              </div>
              <span className="text-sm font-semibold" style={{ color: '#10B981', fontWeight: 600 }}>
                System Online
              </span>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <main className="flex-1 overflow-auto p-8">
          <AnimatePresence mode="wait">
            {activeTab === 'dashboard' && (
              <motion.div
                key="dashboard"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="space-y-8"
              >
                {/* Stats Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {stats.map((stat, index) => (
                    <motion.div
                      key={stat.label}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: 0.1 * index }}
                      className="p-5 rounded-2xl relative overflow-hidden group"
                      style={{
                        background: 'linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%)',
                        border: '1px solid rgba(255,255,255,0.06)'
                      }}
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div
                          className="w-11 h-11 rounded-xl flex items-center justify-center"
                          style={{
                            background: 'linear-gradient(135deg, rgba(139,92,246,0.2) 0%, rgba(168,85,247,0.1) 100%)',
                            border: '1px solid rgba(139,92,246,0.2)',
                            color: '#8B5CF6'
                          }}
                        >
                          <stat.icon size={20} />
                        </div>
                        <span
                          className="text-xs font-medium px-2 py-1 rounded-lg"
                          style={{
                            backgroundColor: stat.trend === 'up' ? 'rgba(16,185,129,0.15)' : stat.trend === 'down' ? 'rgba(239,68,68,0.15)' : 'rgba(107,114,128,0.15)',
                            color: stat.trend === 'up' ? '#10B981' : stat.trend === 'down' ? '#EF4444' : '#6B7280',
                            fontWeight: 500
                          }}
                        >
                          {stat.change}
                        </span>
                      </div>
                      <div>
                        <p className="text-3xl font-bold mb-1" style={{ color: '#FFFFFF', fontWeight: 600 }}>
                          {stat.value}
                        </p>
                        <p className="text-sm" style={{ color: '#6B7280', fontWeight: 500 }}>
                          {stat.label}
                        </p>
                      </div>
                      <div
                        className="absolute bottom-0 right-0 w-32 h-32 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition-opacity"
                        style={{
                          background: 'radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)'
                        }}
                      />
                    </motion.div>
                  ))}
                </div>

                {/* Hero Section */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: 0.2 }}
                  className="p-8 rounded-3xl relative overflow-hidden"
                  style={{
                    background: 'linear-gradient(135deg, rgba(139,92,246,0.1) 0%, rgba(168,85,247,0.05) 100%)',
                    border: '1px solid rgba(139,92,246,0.15)'
                  }}
                >
                  <div
                    className="absolute top-0 right-0 w-96 h-96 rounded-full blur-3xl opacity-30"
                    style={{
                      background: 'radial-gradient(circle, rgba(139,92,246,0.4) 0%, transparent 70%)'
                    }}
                  />
                  <div className="relative z-10 flex items-center justify-between">
                    <div className="max-w-xl">
                      <div className="flex items-center gap-2 mb-4">
                        <span className="px-3 py-1 rounded-full text-xs font-semibold" style={{
                          backgroundColor: 'rgba(139,92,246,0.2)',
                          color: '#A855F7',
                          border: '1px solid rgba(139,92,246,0.3)',
                          fontWeight: 600
                        }}>
                          New Feature
                        </span>
                        <span className="text-xs" style={{ color: '#6B7280' }}>
                          Updated 2 hours ago
                        </span>
                      </div>
                      <h3 className="text-3xl font-bold mb-3" style={{ color: '#FFFFFF', fontWeight: 600, letterSpacing: '-0.02em' }}>
                        Welcome to PromptAI
                      </h3>
                      <p className="text-base mb-6" style={{ color: '#9CA3AF', lineHeight: 1.6 }}>
                        Your comprehensive AI testing platform for evaluating and improving model performance across production scenarios.
                      </p>
                      <div className="flex items-center gap-3">
                        <motion.button
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                          className="px-6 py-3 rounded-xl text-white font-semibold flex items-center gap-2 transition-all duration-200"
                          style={{
                            background: 'linear-gradient(90deg, #8B5CF6 0%, #A855F7 100%)',
                            boxShadow: '0 8px 24px rgba(139,92,246,0.3)',
                            fontSize: '15px',
                            fontWeight: 600
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'linear-gradient(90deg, #A855F7 0%, #C084FC 100%)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'linear-gradient(90deg, #8B5CF6 0%, #A855F7 100%)';
                          }}
                        >
                          <Zap size={18} />
                          <span>Get Started</span>
                        </motion.button>
                        <motion.button
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                          className="px-6 py-3 rounded-xl text-white font-semibold flex items-center gap-2 transition-all duration-200"
                          style={{
                            backgroundColor: 'rgba(255,255,255,0.05)',
                            border: '1px solid rgba(255,255,255,0.1)',
                            fontSize: '15px',
                            fontWeight: 600
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)';
                          }}
                        >
                          <span>Learn More</span>
                          <ArrowRight size={16} />
                        </motion.button>
                      </div>
                    </div>
                    <div className="hidden lg:block">
                      <div
                        className="w-64 h-64 rounded-3xl flex items-center justify-center relative"
                        style={{
                          background: 'linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(168,85,247,0.05) 100%)',
                          border: '1px solid rgba(139,92,246,0.2)'
                        }}
                      >
                        <Sparkles size={80} style={{ color: '#8B5CF6', opacity: 0.8 }} />
                      </div>
                    </div>
                  </div>
                </motion.div>

                {/* Available Tests Section */}
                <div>
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <h4 className="text-xl font-bold" style={{ color: '#FFFFFF', fontWeight: 600 }}>
                        Available Tests
                      </h4>
                      <p className="text-sm" style={{ color: '#6B7280' }}>
                        Select a test to evaluate your AI model
                      </p>
                    </div>
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      className="px-4 py-2 rounded-lg text-white font-medium flex items-center gap-2 transition-all duration-200"
                      style={{
                        backgroundColor: 'rgba(139,92,246,0.15)',
                        border: '1px solid rgba(139,92,246,0.3)',
                        fontSize: '14px',
                        fontWeight: 500
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = 'rgba(139,92,246,0.25)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'rgba(139,92,246,0.15)';
                      }}
                    >
                      <Plus size={16} />
                      <span>Create Test</span>
                    </motion.button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.3, delay: 0.3 }}
                      className="group cursor-pointer"
                      style={{
                        background: 'linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%)',
                        border: '1px solid rgba(255,255,255,0.06)',
                        borderRadius: '20px',
                        padding: '28px',
                        transition: 'all 0.3s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = 'rgba(139,92,246,0.3)';
                        e.currentTarget.style.transform = 'translateY(-4px)';
                        e.currentTarget.style.boxShadow = '0 20px 40px rgba(139,92,246,0.1)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)';
                        e.currentTarget.style.transform = 'translateY(0)';
                        e.currentTarget.style.boxShadow = 'none';
                      }}
                    >
                      <div className="flex items-start justify-between mb-6">
                        <div
                          className="w-14 h-14 rounded-xl flex items-center justify-center transition-all duration-300"
                          style={{
                            background: 'linear-gradient(135deg, rgba(139,92,246,0.2) 0%, rgba(168,85,247,0.1) 100%)',
                            border: '1px solid rgba(139,92,246,0.2)',
                            color: '#8B5CF6'
                          }}
                        >
                          <testCard.icon size={28} />
                        </div>
                        <div className="flex items-center gap-2">
                          <span
                            className="px-2.5 py-1 rounded-full text-xs font-medium"
                            style={{
                              backgroundColor: 'rgba(16,185,129,0.15)',
                              color: '#10B981',
                              border: '1px solid rgba(16,185,129,0.2)',
                              fontWeight: 600
                            }}
                          >
                            {testCard.status}
                          </span>
                          <button className="p-1.5 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#6B7280' }}>
                            <MoreHorizontal size={16} />
                          </button>
                        </div>
                      </div>
                      <h5 className="text-xl font-bold mb-3" style={{ color: '#FFFFFF', fontWeight: 600, letterSpacing: '-0.01em' }}>
                        {testCard.title}
                      </h5>
                      <p className="text-sm mb-5" style={{ color: '#9CA3AF', lineHeight: 1.6 }}>
                        {testCard.description}
                      </p>
                      <div className="flex items-center gap-3 mb-5">
                        <div className="flex items-center gap-1.5">
                          <div
                            className="w-1.5 h-1.5 rounded-full"
                            style={{ backgroundColor: testCard.difficulty === 'Beginner' ? '#10B981' : testCard.difficulty === 'Intermediate' ? '#F59E0B' : '#EF4444' }}
                          />
                          <span className="text-xs font-medium" style={{ color: '#6B7280', fontWeight: 500 }}>
                            {testCard.difficulty}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <Clock size={14} style={{ color: '#6B7280' }} />
                          <span className="text-xs font-medium" style={{ color: '#6B7280', fontWeight: 500 }}>
                            {testCard.duration}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#8B5CF6' }} />
                          <span className="text-xs font-medium" style={{ color: '#6B7280', fontWeight: 500 }}>
                            {testCard.category}
                          </span>
                        </div>
                      </div>
                      <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        className="w-full py-3 rounded-xl text-white font-semibold flex items-center justify-center gap-2 transition-all duration-200"
                        style={{
                          background: 'linear-gradient(90deg, #8B5CF6 0%, #A855F7 100%)',
                          boxShadow: '0 8px 20px rgba(139,92,246,0.25)',
                          fontSize: '15px',
                          fontWeight: 600
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = 'linear-gradient(90deg, #A855F7 0%, #C084FC 100%)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = 'linear-gradient(90deg, #8B5CF6 0%, #A855F7 100%)';
                        }}
                      >
                        <span>Start Test</span>
                        <ArrowRight size={18} />
                      </motion.button>
                    </motion.div>

                    {/* Add more test cards as placeholder */}
                    {[
                      { title: 'Chatbot Response', description: 'Evaluate conversational AI responses for accuracy and relevance.', icon: MessageSquare, difficulty: 'Advanced', duration: '20 min' },
                      { title: 'Content Generation', description: 'Test AI model\'s ability to generate high-quality written content.', icon: Sparkles, difficulty: 'Intermediate', duration: '25 min' }
                    ].map((test, index) => (
                      <motion.div
                        key={test.title}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.3, delay: 0.4 + index * 0.1 }}
                        className="group cursor-pointer opacity-50"
                        style={{
                          background: 'linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%)',
                          border: '1px solid rgba(255,255,255,0.06)',
                          borderRadius: '20px',
                          padding: '28px'
                        }}
                      >
                        <div className="flex items-start justify-between mb-6">
                          <div
                            className="w-14 h-14 rounded-xl flex items-center justify-center"
                            style={{
                              background: 'linear-gradient(135deg, rgba(107,114,128,0.15) 0%, rgba(107,114,128,0.05) 100%)',
                              border: '1px solid rgba(107,114,128,0.15)',
                              color: '#6B7280'
                            }}
                          >
                            <test.icon size={28} />
                          </div>
                          <div className="flex items-center gap-2">
                            <span
                              className="px-2.5 py-1 rounded-full text-xs font-medium"
                              style={{
                                backgroundColor: 'rgba(107,114,128,0.15)',
                                color: '#6B7280',
                                border: '1px solid rgba(107,114,128,0.15)',
                                fontWeight: 600
                              }}
                            >
                              Coming Soon
                            </span>
                          </div>
                        </div>
                        <h5 className="text-xl font-bold mb-3" style={{ color: '#FFFFFF', fontWeight: 600, letterSpacing: '-0.01em' }}>
                          {test.title}
                        </h5>
                        <p className="text-sm mb-5" style={{ color: '#9CA3AF', lineHeight: 1.6 }}>
                          {test.description}
                        </p>
                        <div className="flex items-center gap-3 mb-5">
                          <div className="flex items-center gap-1.5">
                            <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#6B7280' }} />
                            <span className="text-xs font-medium" style={{ color: '#6B7280', fontWeight: 500 }}>
                              {test.difficulty}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Clock size={14} style={{ color: '#6B7280' }} />
                            <span className="text-xs font-medium" style={{ color: '#6B7280', fontWeight: 500 }}>
                              {test.duration}
                            </span>
                          </div>
                        </div>
                        <button
                          disabled
                          className="w-full py-3 rounded-xl text-white font-semibold flex items-center justify-center gap-2"
                          style={{
                            backgroundColor: 'rgba(107,114,128,0.15)',
                            border: '1px solid rgba(107,114,128,0.2)',
                            fontSize: '15px',
                            fontWeight: 600,
                            color: '#6B7280',
                            cursor: 'not-allowed'
                          }}
                        >
                          <span>Coming Soon</span>
                        </button>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === 'tests' && (
              <motion.div
                key="tests"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-center py-32"
              >
                <div className="mb-6 inline-flex items-center justify-center w-24 h-24 rounded-2xl" style={{
                  background: 'linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(168,85,247,0.05) 100%)',
                  border: '1px solid rgba(139,92,246,0.2)'
                }}>
                  <FlaskConical size={48} style={{ color: '#8B5CF6' }} />
                </div>
                <h3 className="text-3xl font-bold mb-3" style={{ color: '#FFFFFF', fontWeight: 600 }}>
                  AI Model Tests
                </h3>
                <p className="text-lg" style={{ color: '#6B7280' }}>
                  Comprehensive testing suite coming soon
                </p>
              </motion.div>
            )}

            {activeTab === 'feedback' && (
              <motion.div
                key="feedback"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-center py-32"
              >
                <div className="mb-6 inline-flex items-center justify-center w-24 h-24 rounded-2xl" style={{
                  background: 'linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(168,85,247,0.05) 100%)',
                  border: '1px solid rgba(139,92,246,0.2)'
                }}>
                  <MessageSquare size={48} style={{ color: '#8B5CF6' }} />
                </div>
                <h3 className="text-3xl font-bold mb-3" style={{ color: '#FFFFFF', fontWeight: 600 }}>
                  User Feedback
                </h3>
                <p className="text-lg" style={{ color: '#6B7280' }}>
                  Collect and analyze user insights
                </p>
              </motion.div>
            )}

            {activeTab === 'reports' && (
              <motion.div
                key="reports"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-center py-32"
              >
                <div className="mb-6 inline-flex items-center justify-center w-24 h-24 rounded-2xl" style={{
                  background: 'linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(168,85,247,0.05) 100%)',
                  border: '1px solid rgba(139,92,246,0.2)'
                }}>
                  <BarChart size={48} style={{ color: '#8B5CF6' }} />
                </div>
                <h3 className="text-3xl font-bold mb-3" style={{ color: '#FFFFFF', fontWeight: 600 }}>
                  Analytics Reports
                </h3>
                <p className="text-lg" style={{ color: '#6B7280' }}>
                  Detailed performance metrics and insights
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </main>
      </div>

      {/* Logout Modal */}
      <LogoutModal
        isOpen={showLogoutModal}
        onClose={cancelLogout}
        onConfirm={confirmLogout}
      />
    </div>
  );
};

export default Home;