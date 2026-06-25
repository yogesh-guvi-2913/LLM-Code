import { useAuth } from '../contexts/AuthContext';

const Home = () => {
  const { logout } = useAuth();

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-premium-gradient relative overflow-hidden">
      {/* Ambient purple glow background */}
      <div className="absolute inset-0 bg-purple-glow pointer-events-none"></div>

      {/* Floating decorative elements */}
      <div className="absolute top-20 left-20 w-64 h-64 bg-secondary/10 rounded-full blur-3xl animate-float"></div>
      <div className="absolute bottom-20 right-20 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-float" style={{ animationDelay: '2s' }}></div>

      {/* Main content */}
      <div className="relative z-10 text-center max-w-2xl px-6">
        {/* Welcome icon */}
        <div className="inline-flex items-center justify-center w-24 h-24 bg-gradient-to-br from-secondary to-accent rounded-2xl mb-8 shadow-glow-lg">
          <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>

        <h1 className="text-5xl md:text-6xl font-bold text-white mb-4">
          Welcome Back
        </h1>

        <p className="text-xl text-gray-400 mb-8">
          You've successfully authenticated to the platform
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
          <button
            onClick={logout}
            className="px-8 py-3 bg-white/5 border border-white/10 text-white rounded-lg font-semibold hover:bg-white/10 transition-all duration-300 hover:shadow-glow"
          >
            Logout
          </button>
          <button className="px-8 py-3 bg-gradient-to-r from-secondary to-accent text-white rounded-lg font-semibold hover:from-secondary/90 hover:to-accent/90 transition-all duration-300 shadow-glow hover:shadow-glow-lg transform hover:scale-105">
            Explore Features
          </button>
        </div>
      </div>

      {/* Premium branding footer */}
      <div className="absolute bottom-8 text-center">
        <p className="text-gray-500 text-sm">
          Powered by{' '}
          <span className="text-accent font-semibold">AI Intelligence</span>
        </p>
      </div>
    </div>
  );
};

export default Home;