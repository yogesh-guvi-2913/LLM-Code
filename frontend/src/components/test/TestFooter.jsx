import { CheckCircle, Play, RefreshCw, Send, Zap, Trophy } from 'lucide-react';
import { useTest } from '../../contexts/TestContext';

function TestFooter() {
  const {
    testData,
    answers,
    handleSubmitTest,
    handleFlashSubmit,
    isSubmitting,
    sessionType,
    sessionInfo,
    scoreResult,
  } = useTest();

  const isFlash = sessionType === 'flash';

  return (
    <footer className="px-4 py-3 border-t border-white/[0.06] bg-[#0a0a0b]/80 backdrop-blur-xl flex items-center justify-between">
      <div className="flex items-center gap-3">
        {scoreResult && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-300">
            <Trophy size={14} />
            <span className="text-xs font-bold">{scoreResult.score}/{scoreResult.maxScore} ({scoreResult.percentage.toFixed(1)}%)</span>
          </div>
        )}
        {!isFlash && (
          <>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <CheckCircle size={14} />
              <span className="text-xs font-medium">{Object.keys(answers).length} answered</span>
            </div>
            <div className="text-xs text-gray-500">
              of {testData?.questions?.length || 0} questions
            </div>
          </>
        )}
        {isFlash && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <Zap size={14} />
            <span className="text-xs font-medium">Flash Sandbox Test</span>
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => window.history.back()}
          className="px-4 py-2 rounded-lg font-medium text-sm bg-white/[0.05] border border-white/[0.1] text-gray-400 hover:bg-white/[0.08] hover:text-gray-300 transition-all"
        >
          Cancel
        </button>
        {isFlash ? (
          <button
            onClick={handleFlashSubmit}
            disabled={isSubmitting || !sessionInfo?.sessionId}
            className="px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 bg-gradient-to-r from-amber-600 to-amber-500 text-white hover:from-amber-500 hover:to-amber-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? (
              <>
                <RefreshCw size={14} className="animate-spin" />
                <span>Submitting...</span>
              </>
            ) : (
              <>
                <Send size={14} />
                <span>Submit & Score</span>
              </>
            )}
          </button>
        ) : (
          <button
            onClick={handleSubmitTest}
            disabled={isSubmitting}
            className="px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 bg-gradient-to-r from-violet-600 to-violet-500 text-white hover:from-violet-500 hover:to-violet-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? (
              <>
                <RefreshCw size={14} className="animate-spin" />
                <span>Submitting...</span>
              </>
            ) : (
              <>
                <Play size={14} />
                <span>Submit Test</span>
              </>
            )}
          </button>
        )}
      </div>
    </footer>
  );
}

export default TestFooter;