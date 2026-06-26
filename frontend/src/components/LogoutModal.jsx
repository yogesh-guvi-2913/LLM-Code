import { motion, AnimatePresence } from 'framer-motion';
import { LogOut } from 'lucide-react';

const LogoutModal = ({ isOpen, onClose, onConfirm }) => {
  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0"
            style={{
              backgroundColor: 'rgba(0, 0, 0, 0.7)',
              backdropFilter: 'blur(4px)'
            }}
          />

      {/* Modal */}
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        transition={{ duration: 0.2 }}
        className="relative w-full max-w-md mx-4"
        style={{
          backgroundColor: '#161616',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: '20px',
          padding: '32px',
          boxShadow: '0 25px 50px rgba(0,0,0,0.5)'
        }}
      >
        {/* Icon */}
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6"
          style={{
            background: 'linear-gradient(135deg, rgba(239,68,68,0.15) 0%, rgba(239,68,68,0.05) 100%)',
            border: '1px solid rgba(239,68,68,0.2)'
          }}
        >
          <LogOut size={32} style={{ color: '#EF4444' }} />
        </div>

        {/* Title */}
        <h2
          className="text-2xl font-bold text-center mb-3"
          style={{ color: '#FFFFFF', fontWeight: 600 }}
        >
          Confirm Logout
        </h2>

        {/* Description */}
        <p
          className="text-center mb-8"
          style={{ color: '#9CA3AF', lineHeight: 1.6 }}
        >
          Are you sure you want to logout? You will need to sign in again to access your account.
        </p>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-3 px-6 rounded-xl text-white font-semibold transition-all duration-200"
            style={{
              backgroundColor: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.1)',
              fontSize: '16px',
              fontWeight: 600
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)';
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 py-3 px-6 rounded-xl text-white font-semibold transition-all duration-200"
            style={{
              background: 'linear-gradient(90deg, #EF4444 0%, #DC2626 100%)',
              boxShadow: '0 8px 24px rgba(239,68,68,0.3)',
              fontSize: '16px',
              fontWeight: 600
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'linear-gradient(90deg, #DC2626 0%, #B91C1C 100%)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'linear-gradient(90deg, #EF4444 0%, #DC2626 100%)';
            }}
          >
            Logout
          </button>
        </div>
      </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

export default LogoutModal;