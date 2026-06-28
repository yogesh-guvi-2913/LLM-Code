import { Terminal as TerminalIcon, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { useTest } from '../../contexts/TestContext';

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
    previewErrors
  } = useTest();

  return (
    <div className={`border-t border-white/[0.06] bg-[#0a0a0b] flex flex-col ${showTerminal ? 'h-[200px]' : ''}`}>
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/[0.06] bg-[#0d0d0e]">
        <div className="flex items-center gap-1">
          {['terminal', 'output', 'problems'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTerminalTab(tab)}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTerminalTab === tab
                  ? 'text-white bg-white/[0.08]'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab === 'terminal' && <TerminalIcon size={12} />}
              <span className="capitalize">{tab}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setTerminalLines([])}
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
        <div ref={terminalEndRef} className="flex-1 overflow-y-auto custom-scrollbar p-3 font-mono text-xs leading-relaxed">
          {activeTerminalTab === 'terminal' && (
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
                <div className="text-gray-500 italic">No output yet. Run your code to see output here.</div>
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
