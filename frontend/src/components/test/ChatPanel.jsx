import { useState, useEffect, useRef } from 'react';
import { MessageSquare, Play, Wifi, WifiOff, Lightbulb, Loader2, CheckCircle, Package } from 'lucide-react';
import { useTest } from '../../contexts/TestContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function extractPackageName(command) {
  const match = command.match(/(?:npm install|npm i|yarn add|pnpm add)\s+(?:-S\s+|-D\s+)?(.+)/);
  if (!match) return null;
  const packages = match[1].trim().split(/\s+/).filter(p => !p.startsWith('-'));
  return packages.join(', ');
}

function AutoCommand({ command, sessionInfo, authToken, isLoading }) {
  const [status, setStatus] = useState(isLoading ? 'pending' : 'idle');
  const executedRef = useRef(false);

  useEffect(() => {
    if (isLoading || executedRef.current) return;
    if (!sessionInfo?.sessionId || !authToken) return;

    executedRef.current = true;
    setStatus('running');

    fetch(`${API_BASE_URL}/session/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        authToken,
        sessionId: sessionInfo.sessionId,
        command,
        service: 'frontend'
      })
    })
      .then(res => res.json())
      .then(data => setStatus(data.success ? 'done' : 'failed'))
      .catch(() => setStatus('failed'));
  }, [isLoading, sessionInfo, authToken, command]);

  const packageName = extractPackageName(command);

  if (isLoading) return null;

  return (
    <div className="flex items-center gap-1.5 text-sm text-gray-500 my-0.5">
      {status === 'running' ? (
        <>
          <Loader2 size={12} className="text-violet-400 animate-spin" />
          <span className="text-gray-500">Installing <span className="text-gray-300 font-medium">{packageName || command}</span>...</span>
        </>
      ) : status === 'done' ? (
        <>
          <CheckCircle size={12} className="text-emerald-500" />
          <span className="text-gray-500">Installed <span className="text-gray-300 font-medium">{packageName || command}</span></span>
        </>
      ) : status === 'failed' ? (
        <>
          <Package size={12} className="text-red-400" />
          <span className="text-gray-500">Failed to install <span className="text-gray-300 font-medium">{packageName || command}</span></span>
        </>
      ) : null}
    </div>
  );
}

function InstalledPackages({ packages }) {
  if (!packages || packages.length === 0) return null;
  
  return packages.map((pkg, index) => (
    <div key={`pkg-${index}`} className="flex items-center gap-1.5 text-sm text-gray-500 my-0.5">
      <CheckCircle size={12} className="text-emerald-500" />
      <span className="text-gray-500">Installed <span className="text-gray-300 font-medium">{pkg}</span></span>
    </div>
  ));
}

function renderMarkdownWithFiles(rawContent, isLoading, sessionInfo, authToken) {
  if (!rawContent) return null;
  
  const elements = [];
  const combinedRegex = /```(file|delete|bash|shell|sh):?([^\n]*)\n?([\s\S]*?)```/g;
  
  let lastIndex = 0;
  let match;
  let fileIndex = 0;
  
  while ((match = combinedRegex.exec(rawContent)) !== null) {
    const textBefore = rawContent.substring(lastIndex, match.index);
    if (textBefore.trim()) {
      renderText(textBefore, elements, lastIndex);
    }
    
    const blockType = match[1];
    const blockMeta = match[2].trim();
    const blockContent = match[3].trim();
    
    if (blockType === 'file' || blockType === 'delete') {
      const fileName = blockMeta.split('/').pop();
      const isComponent = /\.(jsx|tsx)$/i.test(blockMeta);
      const actionLabel = blockType === 'delete' ? 'Deleted' : 'Created';
      
      elements.push(
        <div key={`file-${fileIndex}`} className="flex items-center gap-1.5 text-sm text-gray-500 my-0.5">
          <CheckCircle size={12} className="text-emerald-500" />
          <span className="text-gray-500">{actionLabel} <span className="text-gray-300 font-medium">{fileName}</span>{isComponent ? ' component' : ''}</span>
        </div>
      );
      fileIndex++;
    } else if (blockType === 'bash' || blockType === 'shell' || blockType === 'sh') {
      const command = blockContent || blockMeta;
      if (command) {
        elements.push(
          <AutoCommand key={`cmd-${fileIndex}`} command={command} sessionInfo={sessionInfo} authToken={authToken} isLoading={isLoading} />
        );
        fileIndex++;
      }
    }
    
    lastIndex = match.index + match[0].length;
  }
  
  const remaining = rawContent.substring(lastIndex);
  
  const partialTypedMatch = remaining.match(/```(file|delete):([^\n]+)\n?([\s\S]*)$/);
  const partialBashMatch = !partialTypedMatch ? remaining.match(/```(?:bash|shell|sh):?([^\n]*)\n?([\s\S]*)$/) : null;
  const partialPlainMatch = !partialTypedMatch && !partialBashMatch ? remaining.match(/```[a-z]*\n?([\s\S]*)$/) : null;
  
  if (partialTypedMatch) {
    const textBeforePartial = remaining.substring(0, partialTypedMatch.index);
    if (textBeforePartial.trim()) {
      renderText(textBeforePartial, elements, lastIndex);
    }
    
    const path = partialTypedMatch[2].trim();
    const fileName = path.split('/').pop();
    const isComponent = /\.(jsx|tsx)$/i.test(path);
    
    elements.push(
      <div key={`file-${fileIndex}`} className="flex items-center gap-1.5 text-sm text-gray-500 my-0.5">
        <Loader2 size={12} className="text-violet-400 animate-spin" />
        <span className="text-gray-500">{partialTypedMatch[1] === 'delete' ? 'Deleting' : 'Writing'} {fileName}{isComponent ? ' component' : ''}...</span>
      </div>
    );
  } else if (partialBashMatch) {
    const textBeforePartial = remaining.substring(0, partialBashMatch.index);
    if (textBeforePartial.trim()) {
      renderText(textBeforePartial, elements, lastIndex);
    }
  } else if (partialPlainMatch) {
    const textBeforePartial = remaining.substring(0, partialPlainMatch.index);
    if (textBeforePartial.trim()) {
      renderText(textBeforePartial, elements, lastIndex);
    }
  } else if (remaining.trim()) {
    renderText(remaining, elements, lastIndex);
  }
  
  return <div className="space-y-1">{elements}</div>;
}

function renderText(text, elements, baseKey) {
  const lines = text.split('\n');
  
  lines.forEach((line, i) => {
    const key = `${baseKey}-${i}`;
    if (line.startsWith('### ')) {
      elements.push(
        <h3 key={key} className="font-semibold text-gray-200 text-sm mt-3 mb-1">{line.replace(/^### /, '')}</h3>
      );
    } else if (line.startsWith('## ')) {
      elements.push(
        <h2 key={key} className="font-bold text-gray-100 text-base mt-3 mb-1">{line.replace(/^## /, '')}</h2>
      );
    } else if (line.startsWith('# ')) {
      elements.push(
        <h1 key={key} className="font-bold text-gray-100 text-lg mt-3 mb-1">{line.replace(/^# /, '')}</h1>
      );
    } else if (line.startsWith('- **') || line.startsWith('- ')) {
      const listContent = line.replace(/^- /, '');
      const processed = listContent.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      elements.push(
        <li key={key} className="ml-4 text-gray-300 leading-relaxed" dangerouslySetInnerHTML={{ __html: processed }} />
      );
    } else if (line.startsWith('**') && line.endsWith('**')) {
      elements.push(
        <p key={key} className="font-semibold text-gray-200 mt-2">{line.replace(/\*\*/g, '')}</p>
      );
    } else if (line.trim() === '') {
      return;
    } else {
      const processed = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      elements.push(
        <p key={key} className="text-gray-300 leading-relaxed" dangerouslySetInnerHTML={{ __html: processed }} />
      );
    }
  });
}

export function ChatPanel() {
  const {
    chatMessages,
    inputMessage,
    setInputMessage,
    isTyping,
    handleSendMessage,
    wsConnected,
    sessionInfo,
    authToken
  } = useTest();

  const isFirstMessage = (index) => index === 0 && chatMessages[0]?.role === 'assistant';

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
            <div key={index}>
              {isFirstMessage(index) ? (
                <div className="w-full">
                  <div className="flex items-center gap-2 mb-2">
                    <Lightbulb size={14} className="text-amber-400" />
                    <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">Getting Started</span>
                  </div>
                  <div className="text-sm leading-relaxed">{renderMarkdownWithFiles(msg.rawContent || msg.content, msg.streaming, sessionInfo, authToken)}
                    <InstalledPackages packages={msg.installedPackages} />
                  </div>
                </div>
              ) : msg.role === 'user' ? (
                <div className="flex gap-3 flex-row-reverse">
                  <div className="w-8 h-8 rounded-lg bg-violet-500/20 flex items-center justify-center flex-shrink-0">
                    <div className="w-4 h-4 rounded-full bg-violet-500" />
                  </div>
                  <div className="flex-1 max-w-[85%] text-right">
                    <div className="inline-block px-4 py-2 rounded-2xl text-sm text-left bg-violet-500/10 border border-violet-500/20 text-gray-200">
                      <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="w-full text-sm leading-relaxed">
                  {renderMarkdownWithFiles(msg.rawContent || msg.content, msg.streaming, sessionInfo, authToken)}
                  <InstalledPackages packages={msg.installedPackages} />
                </div>
              )}
            </div>
          ))}
          {isTyping && (
            <div className="flex gap-1">
              <div className="w-2 h-2 rounded-full bg-violet-500 animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-2 h-2 rounded-full bg-violet-500 animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-2 h-2 rounded-full bg-violet-500 animate-bounce" style={{ animationDelay: '300ms' }} />
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
