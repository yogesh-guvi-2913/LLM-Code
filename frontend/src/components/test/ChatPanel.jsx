import { MessageSquare, Sparkles, Play, Wifi, WifiOff } from 'lucide-react';
import { useTest } from '../../contexts/TestContext';

export function ChatPanel() {
  const {
    chatMessages,
    inputMessage,
    setInputMessage,
    isTyping,
    handleSendMessage,
    wsConnected
  } = useTest();

  return (
    <div className="flex-1 min-w-[350px] max-w-[500px] border-r border-white/[0.06] flex flex-col">
      <div className="px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <MessageSquare size={14} className="text-violet-400" />
          <span className="text-sm font-semibold text-white">Chat</span>
          <span className="ml-auto flex items-center gap-1.5 text-xs text-gray-500">
            {wsConnected ? (
              <>
                <Wifi size={12} className="text-emerald-500" />
                <span className="text-emerald-500/70">Connected</span>
              </>
            ) : (
              <>
                <WifiOff size={12} className="text-amber-500" />
                <span className="text-amber-500/70">Connecting...</span>
              </>
            )}
          </span>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="p-4 space-y-4">
          {chatMessages.map((msg, index) => (
            <div
              key={index}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                msg.role === 'user' ? 'bg-violet-500/20' : 'bg-emerald-500/20'
              }`}>
                {msg.role === 'user' ? (
                  <div className="w-4 h-4 rounded-full bg-violet-500" />
                ) : (
                  <Sparkles size={16} className="text-emerald-400" />
                )}
              </div>
              <div className={`flex-1 max-w-[85%] ${msg.role === 'user' ? 'text-right' : ''}`}>
                <div className={`inline-block px-4 py-2 rounded-2xl text-sm text-left ${
                  msg.role === 'user'
                    ? 'bg-violet-500/10 border border-violet-500/20 text-gray-200'
                    : 'bg-white/[0.03] border border-white/[0.06] text-gray-300'
                }`}>
                  <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                </div>
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                <Sparkles size={16} className="text-emerald-400" />
              </div>
              <div className="bg-white/[0.03] border border-white/[0.06] px-4 py-2 rounded-2xl">
                <div className="flex gap-1">
                  <div className="w-2 h-2 rounded-full bg-violet-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 rounded-full bg-violet-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 rounded-full bg-violet-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="p-4 border-t border-white/[0.06]">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Ask for help or clarification..."
            className="flex-1 bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50 transition-colors"
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputMessage.trim() || isTyping}
            className="px-4 py-2.5 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400 hover:bg-violet-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatPanel;
