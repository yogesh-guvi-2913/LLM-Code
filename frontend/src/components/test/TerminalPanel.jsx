import { useEffect, useState, useRef } from 'react';
import { Terminal as TerminalIcon, Trash2, ChevronDown, ChevronUp, Server, AlertCircle, Zap, Send } from 'lucide-react';
import { useTest } from '../../contexts/TestContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');

function TerminalPanel() {
  const {
    showTerminal,
    setShowTerminal,
    terminalLines,
    setTerminalLines,
    terminalInput,
    setTerminalInput,
    handleTerminalCommand,
    activeTerminalTab,
    setActiveTerminalTab,
    terminalEndRef,
    consoleLogs,
    previewErrors,
    sessionInfo,
    sessionStatus,
    sessionType,
    handleFlashSubmit,
    isSubmitting,
    scoreResult,
  } = useTest();

  const [containerLogs, setContainerLogs] = useState({ frontend: [], backend: [], all: [] });
  const [activeService, setActiveService] = useState('frontend');
  const [flashTerminalLines, setFlashTerminalLines] = useState([]);
  const [flashTerminalInput, setFlashTerminalInput] = useState('');
  const logEndRef = useRef(null);
  const wsRef = useRef(null);
  const flashWsRef = useRef(null);

  useEffect(() => {
    if (!sessionInfo?.sessionId || activeTerminalTab !== 'logs') return;

    const ws = new WebSocket(`${WS_BASE_URL}/ws/session-logs/${sessionInfo.sessionId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }

      const { service, line } = data;

      setContainerLogs(prev => {
        const serviceLogs = prev[service] || [];
        const updated = { ...prev };
        updated[service] = [...serviceLogs, line];
        updated.all = [...prev.all, `[${service}] ${line}`];
        if (updated.all.length > 500) {
          updated.all = updated.all.slice(-500);
        }
        for (const key of Object.keys(updated)) {
          if (key !== 'all' && updated[key].length > 300) {
            updated[key] = updated[key].slice(-300);
          }
        }
        return updated;
      });
    };

    ws.onerror = () => {};
    ws.onclose = () => {};

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [sessionInfo?.sessionId, activeTerminalTab]);

  useEffect(() => {
    if (!sessionInfo?.sessionId || sessionType !== 'flash' || activeTerminalTab !== 'terminal') return;

    const ws = new WebSocket(`${WS_BASE_URL}/ws/flash-terminal/${sessionInfo.sessionId}`);
    flashWsRef.current = ws;

    ws.onopen = () => {
      setFlashTerminalLines(prev => [...prev, { type: 'system', text: 'Connected to Flash terminal' }]);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'output' && data.data) {
          setFlashTerminalLines(prev => [...prev, { type: 'output', text: data.data }]);
        } else if (data.error) {
          setFlashTerminalLines(prev => [...prev, { type: 'error', text: data.error }]);
        }
      } catch {
        setFlashTerminalLines(prev => [...prev, { type: 'output', text: event.data }]);
      }
    };

    ws.onerror = () => {
      setFlashTerminalLines(prev => [...prev, { type: 'error', text: 'Terminal connection error' }]);
    };

    ws.onclose = () => {
      setFlashTerminalLines(prev => [...prev, { type: 'system', text: 'Terminal disconnected' }]);
    };

    return () => {
      ws.close();
      flashWsRef.current = null;
    };
  }, [sessionInfo?.sessionId, sessionType, activeTerminalTab]);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollTop = logEndRef.current.scrollHeight;
    }
  }, [containerLogs, flashTerminalLines]);

  const handleFlashTerminalInput = (e) => {
    if (e.key === 'Enter' && flashTerminalInput.trim() && flashWsRef.current?.readyState === WebSocket.OPEN) {
      flashWsRef.current.send(JSON.stringify({ type: 'input', data: flashTerminalInput + '\n' }));
      setFlashTerminalLines(prev => [...prev, { type: 'input', text: `$ ${flashTerminalInput}` }]);
      setFlashTerminalInput('');
    }
  };

  const isLogsTab = activeTerminalTab === 'logs';
  const currentLogs = containerLogs[activeService] || [];

  return (
    <div className={`border-t border-white/[0.06] bg-[#0a0a0b] flex flex-col ${showTerminal ? 'h-[220px]' : ''}`}>
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/[0.06] bg-[#0d0d0e]">
        <div className="flex items-center gap-1">
          {['logs', 'terminal', 'output', 'problems'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTerminalTab(tab)}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTerminalTab === tab
                  ? 'text-white bg-white/[0.08]'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab === 'logs' && <Server size={12} />}
              {tab === 'terminal' && <TerminalIcon size={12} />}
              <span className="capitalize">{tab}</span>
            </button>
          ))}
          {sessionType === 'flash' && (
            <button
              onClick={handleFlashSubmit}
              disabled={isSubmitting || !sessionInfo?.sessionId}
              className="flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 transition-all disabled:opacity-50"
            >
              <Send size={12} />
              <span>{isSubmitting ? 'Submitting...' : 'Submit & Score'}</span>
            </button>
          )}
        </div>
        <div className="flex items-center gap-1">
          {sessionType === 'flash' && (
            <div className="flex items-center gap-1 px-2 py-0.5 bg-amber-500/10 rounded text-xs text-amber-400">
              <Zap size={10} />
              <span>Flash</span>
            </div>
          )}
          <button
            onClick={() => {
              if (isLogsTab) {
                setContainerLogs({ frontend: [], backend: [], all: [] });
              } else if (sessionType === 'flash' && activeTerminalTab === 'terminal') {
                setFlashTerminalLines([]);
              } else {
                setTerminalLines([]);
              }
            }}
            className="p-1 rounded hover:bg-white/[0.08] transition-colors text-gray-500 hover:text-gray-300"
          >
            <Trash2 size={12} />
          </button>
          <button
            onClick={() => setShowTerminal(!showTerminal)}
            className="p-1 rounded hover:bg-white/[0.08] transition-colors text-gray-500 hover:text-gray-300"
          >
            {showTerminal ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
          </button>
        </div>
      </div>
      {showTerminal && (
        <div
          ref={isLogsTab ? logEndRef : terminalEndRef}
          className="flex-1 overflow-y-auto custom-scrollbar p-3 font-mono text-xs leading-relaxed"
        >
          {isLogsTab && (
            <>
              <div className="flex gap-2 mb-2 pb-2 border-b border-white/5">
                {['frontend', 'backend', 'all'].map(svc => (
                  <button
                    key={svc}
                    onClick={() => setActiveService(svc)}
                    className={`px-2 py-0.5 rounded text-xs transition-all ${
                      activeService === svc
                        ? 'bg-violet-500/20 text-violet-300'
                        : 'text-gray-500 hover:text-gray-300'
                    }`}
                  >
                    {svc.charAt(0).toUpperCase() + svc.slice(1)}
                    {containerLogs[svc]?.length > 0 && (
                      <span className="ml-1 text-[10px] text-gray-600">
                        ({containerLogs[svc].length})
                      </span>
                    )}
                  </button>
                ))}
              </div>
              {currentLogs.length === 0 ? (
                <div className="text-gray-500 italic flex items-center gap-2">
                  {sessionStatus === 'ready' ? (
                    <>
                      <Server size={12} />
                      <span>Waiting for container logs...</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle size={12} />
                      <span>Containers not running.</span>
                    </>
                  )}
                </div>
              ) : (
                currentLogs.map((line, i) => (
                  <div
                    key={i}
                    className={`${
                      line.toLowerCase().includes('error') || line.toLowerCase().includes('fail')
                        ? 'text-red-400'
                        : line.toLowerCase().includes('warn')
                        ? 'text-yellow-400'
                        : 'text-gray-300'
                    }`}
                  >
                    {line}
                  </div>
                ))
              )}
            </>
          )}
          {activeTerminalTab === 'terminal' && sessionType === 'flash' && (
            <>
              {scoreResult && (
                <div className="mb-3 p-2 rounded bg-emerald-500/10 border border-emerald-500/20">
                  <div className="text-emerald-400 font-bold">Score: {scoreResult.score}/{scoreResult.maxScore} ({scoreResult.percentage.toFixed(1)}%)</div>
                </div>
              )}
              {flashTerminalLines.length === 0 ? (
                <div className="text-gray-500 italic">Connected to Flash terminal. Type commands...</div>
              ) : (
                flashTerminalLines.map((line, i) => (
                  <div key={i} className={`${
                    line.type === 'input' ? 'text-emerald-400' :
                    line.type === 'system' ? 'text-violet-400' :
                    line.type === 'error' ? 'text-red-400' :
                    'text-gray-300'
                  }`}>
                    {line.text}
                  </div>
                ))
              )}
              <div className="flex items-center gap-2 mt-1">
                <span className="text-emerald-400">$</span>
                <input
                  type="text"
                  value={flashTerminalInput}
                  onChange={(e) => setFlashTerminalInput(e.target.value)}
                  onKeyDown={handleFlashTerminalInput}
                  className="flex-1 bg-transparent text-gray-200 outline-none"
                  placeholder="Type a command..."
                  autoFocus
                />
              </div>
            </>
          )}
          {activeTerminalTab === 'terminal' && sessionType !== 'flash' && (
            <>
              {terminalLines.map((line, i) => (
                <div key={i} className={`${
                  line.type === 'input' ? 'text-emerald-400' :
                  line.type === 'system' ? 'text-violet-400' :
                  line.type === 'error' ? 'text-red-400' :
                  'text-gray-300'
                }`}>
                  {line.text}
                </div>
              ))}
              <div className="flex items-center gap-2 mt-1">
                <span className="text-emerald-400">$</span>
                <input
                  type="text"
                  value={terminalInput}
                  onChange={(e) => setTerminalInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && terminalInput.trim()) {
                      handleTerminalCommand(terminalInput.trim());
                      setTerminalInput('');
                    }
                  }}
                  className="flex-1 bg-transparent text-gray-200 outline-none"
                  placeholder="Type a command..."
                  autoFocus
                />
              </div>
            </>
          )}
          {activeTerminalTab === 'output' && (
            <>
              {consoleLogs.length === 0 ? (
                <div className="text-gray-500 italic">No output yet. Logs from containers appear in the "Logs" tab.</div>
              ) : (
                consoleLogs.map((log, i) => (
                  <div key={i} className={`${
                    log.level === 'error' ? 'text-red-400' :
                    log.level === 'warn' ? 'text-yellow-400' :
                    'text-gray-300'
                  }`}>
                    {log.level === 'error' ? '[Error] ' : log.level === 'warn' ? '[Warn] ' : ''}
                    {log.message}
                  </div>
                ))
              )}
            </>
          )}
          {activeTerminalTab === 'problems' && (
            <>
              {previewErrors.length === 0 ? (
                <div className="text-emerald-400">No problems detected.</div>
              ) : (
                previewErrors.map((err, i) => (
                  <div key={i} className="text-red-400">
                    {err.message}
                  </div>
                ))
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default TerminalPanel;
