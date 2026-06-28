import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { TestProvider, useTest } from '../contexts/TestContext';
import TestHeader from '../components/test/TestHeader';
import ChatPanel from '../components/test/ChatPanel';
import CodePanel from '../components/test/CodePanel';
import PreviewPanel from '../components/test/PreviewPanel';
import ProblemModal from '../components/test/ProblemModal';
import TestFooter from '../components/test/TestFooter';
import { Code, Eye, Zap } from 'lucide-react';

function TestContent() {
  const { testData, isLoading, activeRightTab, setActiveRightTab } = useTest();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0a0a0b]">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-2 border-violet-500/30"></div>
          <div className="absolute top-0 left-0 w-12 h-12 rounded-full border-2 border-violet-500 animate-spin border-t-transparent"></div>
        </div>
      </div>
    );
  }

  if (!testData) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-screen bg-[#0a0a0b]">
        <div className="text-center text-gray-500">
          <Zap size={32} className="mx-auto mb-3 text-gray-600" />
          <p className="text-sm">Test not found or failed to load</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0b] text-gray-100 font-inter">
      <TestHeader />
      
      <main className="flex-1 flex overflow-hidden">
        <ChatPanel />
        
        <div className="flex-1 flex flex-col">
          <div className="flex items-center gap-1 px-2 py-1.5 border-b border-white/[0.06]">
            {[
              { id: 'code', label: 'Code', icon: Code },
              { id: 'preview', label: 'Preview', icon: Eye }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveRightTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeRightTab === tab.id
                    ? 'bg-violet-500/10 text-violet-400'
                    : 'hover:bg-white/[0.05] text-gray-500 hover:text-gray-300'
                }`}
              >
                <tab.icon size={14} />
                <span>{tab.label}</span>
              </button>
            ))}
            <div className="flex-1" />
            <div className="flex gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/30" />
              <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/20 border border-yellow-500/30" />
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/20 border border-emerald-500/30" />
            </div>
          </div>

          <div className="flex-1 overflow-hidden">
            {activeRightTab === 'code' && <CodePanel />}
            {activeRightTab === 'preview' && <PreviewPanel />}
          </div>
        </div>
      </main>

      <TestFooter />
      <ProblemModal />

      <style>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
          height: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(139, 92, 246, 0.3);
          border-radius: 3px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(139, 92, 246, 0.5);
        }
      `}</style>
    </div>
  );
}

function TestPage() {
  const { testId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <TestProvider testId={testId} authToken={user?.authToken} navigate={navigate}>
      <TestContent />
    </TestProvider>
  );
}

export default TestPage;