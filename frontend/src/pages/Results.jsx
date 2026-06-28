import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import toast from 'react-hot-toast';
import {
  BarChart3,
  Trophy,
  Code2,
  MessageSquare,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Monitor,
  Smartphone,
  FileCode,
  ArrowLeft,
  Loader2,
  Star,
  ChevronDown,
  ChevronUp,
  Target,
  Lightbulb,
  TrendingUp
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function Results() {
  const { testId } = useParams();
  const navigate = useNavigate();
  const { user, logout: authLogout } = useAuth();

  const [isLoading, setIsLoading] = useState(true);
  const [results, setResults] = useState(null);
  const [expandedSection, setExpandedSection] = useState('overview');
  const [showDesktopScreenshot, setShowDesktopScreenshot] = useState(true);

  const fetchResults = useCallback(async () => {
    if (!user?.authToken) return;

    try {
      const response = await fetch(`${API_BASE}/results`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          authToken: user.authToken,
          testId: testId
        })
      });

      const data = await response.json();

      if (response.ok) {
        if (data.detail === 'token_expired') {
          toast.error('Session expired');
          authLogout();
          navigate('/login');
          return;
        }
        setResults(data);
      } else {
        toast.error(data.message || 'Failed to fetch results');
      }
    } catch (error) {
      console.error('Error fetching results:', error);
      toast.error('Failed to fetch results');
    } finally {
      setIsLoading(false);
    }
  }, [user?.authToken, testId, authLogout, navigate]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  useEffect(() => {
    if (results && results.status === 'evaluating') {
      const interval = setInterval(() => fetchResults(), 5000);
      return () => clearInterval(interval);
    }
  }, [results, fetchResults]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-primary flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-violet-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading results...</p>
        </div>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="min-h-screen bg-primary flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <p className="text-gray-400">No results found</p>
          <button
            onClick={() => navigate('/')}
            className="mt-4 px-4 py-2 bg-violet-500/20 rounded-lg text-violet-400 hover:bg-violet-500/30 transition-colors"
          >
            <ArrowLeft className="w-4 h-4 inline mr-2" />
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (results.status === 'evaluating') {
    return (
      <div className="min-h-screen bg-primary flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-violet-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-400 mb-2">Evaluating your submission...</p>
          <p className="text-gray-500 text-sm">This may take a few moments</p>
        </div>
      </div>
    );
  }

  const evaluation = results.evaluation || {};
  const overallScore = evaluation.overallScore || 0;
  const categories = evaluation.categories || [];
  const strengths = evaluation.strengths || [];
  const improvements = evaluation.improvements || [];
  const summary = evaluation.summary || '';

  const scoreColor = overallScore >= 8 ? 'text-emerald-400' : overallScore >= 5 ? 'text-amber-400' : 'text-red-400';
  const scoreBg = overallScore >= 8 ? 'bg-emerald-500/10' : overallScore >= 5 ? 'bg-amber-500/10' : 'bg-red-500/10';

  return (
    <div className="min-h-screen bg-primary">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <button
          onClick={() => navigate('/')}
          className="mb-6 flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft size={18} />
          <span>Back to Dashboard</span>
        </button>

        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-white mb-2">{results.testName || 'Test Results'}</h1>
          <p className="text-gray-400 text-sm">
            Submitted {results.submittedAt ? new Date(results.submittedAt).toLocaleString() : 'recently'}
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className={`lg:col-span-1 ${scoreBg} rounded-xl border border-white/[0.06] p-6 text-center`}>
            <Trophy className="w-8 h-8 text-violet-400 mx-auto mb-3" />
            <div className={`text-5xl font-bold ${scoreColor} mb-2`}>{overallScore.toFixed(1)}</div>
            <p className="text-gray-400 text-sm">Overall Score</p>
            <div className="mt-4 flex justify-center gap-1">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => (
                <Star
                  key={i}
                  size={14}
                  className={i <= Math.round(overallScore) ? 'text-violet-400 fill-violet-400' : 'text-gray-600'}
                />
              ))}
            </div>
          </div>

          <div className="lg:col-span-2 bg-secondary rounded-xl border border-white/[0.06] p-6">
            <h3 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
              <BarChart3 size={16} className="text-violet-400" />
              Category Scores
            </h3>
            <div className="space-y-4">
              {categories.map((cat, idx) => (
                <div key={idx}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-gray-300 text-sm">{cat.name}</span>
                    <span className={`text-sm font-medium ${
                      cat.score >= 8 ? 'text-emerald-400' : cat.score >= 5 ? 'text-amber-400' : 'text-red-400'
                    }`}>
                      {cat.score.toFixed(1)} / {cat.maxScore}
                    </span>
                  </div>
                  <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        cat.score >= 8 ? 'bg-emerald-500' : cat.score >= 5 ? 'bg-amber-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${(cat.score / cat.maxScore) * 100}%` }}
                    />
                  </div>
                  <p className="text-gray-500 text-xs mt-2">{cat.feedback}</p>
                </div>
              ))}
              {categories.length === 0 && (
                <p className="text-gray-500 text-sm">No category scores available</p>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4 mb-8">
          <ExpandableSection
            title="Summary"
            icon={<Target size={16} className="text-violet-400" />}
            expanded={expandedSection === 'summary'}
            onToggle={() => setExpandedSection(expandedSection === 'summary' ? '' : 'summary')}
          >
            <p className="text-gray-300">{summary || 'No summary available'}</p>
          </ExpandableSection>

          <ExpandableSection
            title="Strengths"
            icon={<CheckCircle size={16} className="text-emerald-400" />}
            expanded={expandedSection === 'strengths'}
            onToggle={() => setExpandedSection(expandedSection === 'strengths' ? '' : 'strengths')}
          >
            {strengths.length > 0 ? (
              <ul className="space-y-2">
                {strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-gray-300">
                    <Lightbulb size={14} className="text-emerald-400 mt-0.5" />
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-500">No strengths identified</p>
            )}
          </ExpandableSection>

          <ExpandableSection
            title="Areas for Improvement"
            icon={<TrendingUp size={16} className="text-amber-400" />}
            expanded={expandedSection === 'improvements'}
            onToggle={() => setExpandedSection(expandedSection === 'improvements' ? '' : 'improvements')}
          >
            {improvements.length > 0 ? (
              <ul className="space-y-2">
                {improvements.map((imp, i) => (
                  <li key={i} className="flex items-start gap-2 text-gray-300">
                    <AlertTriangle size={14} className="text-amber-400 mt-0.5" />
                    <span>{imp}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-500">No improvements suggested</p>
            )}
          </ExpandableSection>
        </div>

        {(results.screenshot || results.screenshotMobile) && (
          <div className="bg-secondary rounded-xl border border-white/[0.06] p-6 mb-8">
            <h3 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
              <Monitor size={16} className="text-violet-400" />
              Application Screenshots
            </h3>

            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setShowDesktopScreenshot(true)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  showDesktopScreenshot
                    ? 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
                    : 'bg-white/[0.03] text-gray-400 border border-white/[0.06]'
                }`}
              >
                <Monitor size={14} className="inline mr-1" />
                Desktop
              </button>
              <button
                onClick={() => setShowDesktopScreenshot(false)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  !showDesktopScreenshot
                    ? 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
                    : 'bg-white/[0.03] text-gray-400 border border-white/[0.06]'
                }`}
              >
                <Smartphone size={14} className="inline mr-1" />
                Mobile
              </button>
            </div>

            <div className="rounded-lg border border-white/[0.06] overflow-hidden">
              {showDesktopScreenshot && results.screenshot ? (
                <img
                  src={`data:image/png;base64,${results.screenshot}`}
                  alt="Desktop screenshot"
                  className="w-full"
                />
              ) : !showDesktopScreenshot && results.screenshotMobile ? (
                <img
                  src={`data:image/png;base64,${results.screenshotMobile}`}
                  alt="Mobile screenshot"
                  className="w-full max-w-[375px] mx-auto"
                />
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <AlertTriangle size={24} className="mx-auto mb-2" />
                  No screenshot available
                </div>
              )}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          <div className="bg-secondary rounded-xl border border-white/[0.06] p-4">
            <div className="flex items-center gap-3 mb-2">
              <MessageSquare size={16} className="text-violet-400" />
              <span className="text-sm font-medium text-white">Prompts Sent</span>
            </div>
            <div className="text-2xl font-semibold text-gray-300">{results.promptCount || 0}</div>
            <p className="text-xs text-gray-500 mt-1">Interactions with AI assistant</p>
          </div>

          <div className="bg-secondary rounded-xl border border-white/[0.06] p-4">
            <div className="flex items-center gap-3 mb-2">
              <Code2 size={16} className="text-violet-400" />
              <span className="text-sm font-medium text-white">Files Modified</span>
            </div>
            <div className="text-2xl font-semibold text-gray-300">
              {results.files ? Object.keys(results.files).length : 0}
            </div>
            <p className="text-xs text-gray-500 mt-1">Code files in final submission</p>
          </div>
        </div>

        {results.runtimeError && (
          <div className="bg-red-500/10 rounded-xl border border-red-500/20 p-6 mb-8">
            <h3 className="text-sm font-medium text-red-400 mb-2 flex items-center gap-2">
              <XCircle size={16} />
              Runtime Error
            </h3>
            <pre className="text-xs text-red-300 whitespace-pre-wrap">{results.runtimeError}</pre>
          </div>
        )}

        {results.consoleErrors && results.consoleErrors.length > 0 && (
          <div className="bg-amber-500/10 rounded-xl border border-amber-500/20 p-6 mb-8">
            <h3 className="text-sm font-medium text-amber-400 mb-2 flex items-center gap-2">
              <AlertTriangle size={16} />
              Console Errors ({results.consoleErrors.length})
            </h3>
            <ul className="space-y-2">
              {results.consoleErrors.slice(0, 5).map((err, i) => (
                <li key={i} className="text-xs text-amber-300">{err}</li>
              ))}
            </ul>
          </div>
        )}

        <ExpandableSection
          title="Final Code Files"
          icon={<FileCode size={16} className="text-violet-400" />}
          expanded={expandedSection === 'files'}
          onToggle={() => setExpandedSection(expandedSection === 'files' ? '' : 'files')}
        >
          {results.files && Object.keys(results.files).length > 0 ? (
            <div className="space-y-3">
              {Object.entries(results.files).map(([path, file]) => {
                const content = typeof file === 'object' ? file.content : file;
                const language = typeof file === 'object' ? file.language : 'javascript';
                return (
                  <div key={path} className="bg-white/[0.03] rounded-lg border border-white/[0.06] p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-violet-400">{path}</span>
                      <span className="text-xs text-gray-500">{language}</span>
                    </div>
                    <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap max-h-[200px] overflow-y-auto">
                      {content?.slice(0, 2000) || '(empty)'}
                      {content && content.length > 2000 && '\n... (truncated)'}
                    </pre>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-gray-500">No files in submission</p>
          )}
        </ExpandableSection>
      </div>
    </div>
  );
}

function ExpandableSection({ title, icon, expanded, onToggle, children }) {
  return (
    <div className="bg-secondary rounded-xl border border-white/[0.06]">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm font-medium text-white">{title}</span>
        </div>
        {expanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
      </button>
      {expanded && (
        <div className="px-4 pb-4 pt-2 border-t border-white/[0.06]">
          {children}
        </div>
      )}
    </div>
  );
}

export default Results;