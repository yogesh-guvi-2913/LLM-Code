import { ArrowLeft, Lightbulb, Clock, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTest } from '../../contexts/TestContext';
import { useTestTimer } from '../../hooks/useTestTimer';

export function TestHeader() {
  const navigate = useNavigate();
  const { testData, setShowProblemModal, handleSubmitTest } = useTest();
  const duration = testData?.duration || 1800;

  const { formattedTime, isLowTime, isCritical } = useTestTimer(duration, handleSubmitTest);

  const timerClasses = isCritical
    ? 'bg-red-500/10 border border-red-500/30 text-red-400 animate-pulse'
    : isLowTime
      ? 'bg-yellow-500/10 border border-yellow-500/20 text-yellow-400'
      : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400';

  return (
    <header className="h-14 px-4 flex items-center justify-between border-b border-white/[0.06] bg-[#0a0a0b]/80 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/')}
          className="p-2 rounded-lg hover:bg-white/[0.05] transition-colors group"
        >
          <ArrowLeft size={16} className="text-gray-400 group-hover:text-white transition-colors" />
        </button>
        <div>
          <h1 className="text-sm font-semibold text-white">
            {testData?.name || 'Loading...'}
          </h1>
          <p className="text-xs text-gray-500">
            AI Assessment Platform
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={() => setShowProblemModal(true)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-violet-500/10 border border-violet-500/20 hover:bg-violet-500/20 transition-colors"
        >
          <Lightbulb size={14} className="text-violet-400" />
          <span className="text-xs font-semibold text-violet-400">Problem</span>
        </button>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-violet-500/10 border border-violet-500/20">
          <Sparkles size={14} className="text-violet-400" />
          <span className="text-xs font-semibold text-violet-400">AI Powered</span>
        </div>
        <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${timerClasses}`}>
          <Clock size={12} />
          <span className="text-xs font-medium font-mono">{formattedTime}</span>
        </div>
      </div>
    </header>
  );
}

export default TestHeader;
