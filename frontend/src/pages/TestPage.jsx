import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { ArrowLeft, Lightbulb, Clock, CheckCircle, Play, RefreshCw, MessageSquare, Code, Eye, Sparkles, Zap, X, ChevronRight, ChevronDown, File, Folder, Terminal as TerminalIcon, Trash2, ChevronUp } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import toast from 'react-hot-toast';
import DOMPurify from 'dompurify';
import Editor from '@monaco-editor/react';

const TestPage = () => {
  const { testId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [testData, setTestData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [answers, setAnswers] = useState({});
  const [previewHTML, setPreviewHTML] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showProblemModal, setShowProblemModal] = useState(false);
  const [activeRightTab, setActiveRightTab] = useState('code');
  const [expandedFolders, setExpandedFolders] = useState(['root', 'src', 'src/pages', 'src/components', 'src/contexts', 'src/assets', 'src/utils', 'public']);
  const [selectedFile, setSelectedFile] = useState('src/App.jsx');
  const [showTerminal, setShowTerminal] = useState(true);
  const [terminalLines, setTerminalLines] = useState([
    { type: 'system', text: 'Vite + React project loaded. Type a command and press Enter.' }
  ]);
  const [terminalInput, setTerminalInput] = useState('');
  const [activeTerminalTab, setActiveTerminalTab] = useState('terminal');
  const terminalEndRef = useRef(null);
  const [files, setFiles] = useState({
    'vite.config.js': {
      name: 'vite.config.js',
      language: 'javascript',
      content: `import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})`
    },
    'index.html': {
      name: 'index.html',
      language: 'html',
      content: `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Vite + React</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>`
    },
    'package.json': {
      name: 'package.json',
      language: 'json',
      content: `{
  "name": "vite-react-app",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "vite": "^5.0.0"
  }
}`
    },
    'src/main.jsx': {
      name: 'main.jsx',
      language: 'javascript',
      content: `import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)`
    },
    'src/App.jsx': {
      name: 'App.jsx',
      language: 'javascript',
      content: `import { useState } from 'react'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="App">
      <h1>Vite + React</h1>
      <button onClick={() => setCount(c => c + 1)}>
        count is {count}
      </button>
    </div>
  )
}

export default App`
    },
    'src/App.css': {
      name: 'App.css',
      language: 'css',
      content: `.App {
  max-width: 1280px;
  margin: 0 auto;
  padding: 2rem;
  text-align: center;
}`
    },
    'src/index.css': {
      name: 'index.css',
      language: 'css',
      content: `:root {
  font-family: Inter, system-ui, sans-serif;
  line-height: 1.5;
  color-scheme: light dark;
}

body {
  margin: 0;
  display: flex;
  place-items: center;
  min-width: 320px;
  min-height: 100vh;
}`
    },
    'src/pages/Home.jsx': {
      name: 'Home.jsx',
      language: 'javascript',
      content: `export default function Home() {
  return (
    <div>
      <h1>Home Page</h1>
    </div>
  )
}`
    },
    'src/pages/Login.jsx': {
      name: 'Login.jsx',
      language: 'javascript',
      content: `export default function Login() {
  return (
    <div>
      <h1>Login Page</h1>
    </div>
  )
}`
    },
    'src/components/Navbar.jsx': {
      name: 'Navbar.jsx',
      language: 'javascript',
      content: `export default function Navbar() {
  return (
    <nav>
      <h1>Navbar</h1>
    </nav>
  )
}`
    },
    'src/contexts/AuthContext.jsx': {
      name: 'AuthContext.jsx',
      language: 'javascript',
      content: `import { createContext, useContext, useState } from 'react'

const AuthContext = createContext()

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  return (
    <AuthContext.Provider value={{ user, setUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)`
    },
    'src/utils/api.js': {
      name: 'api.js',
      language: 'javascript',
      content: `const API_BASE = 'http://localhost:8000'

export async function apiFetch(endpoint, options = {}) {
  const res = await fetch(\`\${API_BASE}/\${endpoint}\`, options)
  return res.json()
}`
    },
    'public/vite.svg': {
      name: 'vite.svg',
      language: 'xml',
      content: `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <path fill="#646CFF" d="M16 2L2 16l14 14 14-14z"/>
</svg>`
    }
  });

  const folderTree = {
    'root': {
      name: 'project',
      folders: {
        'src': {
          name: 'src',
          folders: {
            'pages': { name: 'pages', folders: {}, files: ['src/pages/Home.jsx', 'src/pages/Login.jsx'] },
            'components': { name: 'components', folders: {}, files: ['src/components/Navbar.jsx'] },
            'contexts': { name: 'contexts', folders: {}, files: ['src/contexts/AuthContext.jsx'] },
            'utils': { name: 'utils', folders: {}, files: ['src/utils/api.js'] },
            'assets': { name: 'assets', folders: {}, files: [] }
          },
          files: ['src/main.jsx', 'src/App.jsx', 'src/App.css', 'src/index.css']
        },
        'public': { name: 'public', folders: {}, files: ['public/vite.svg'] }
      },
      files: ['vite.config.js', 'index.html', 'package.json']
    }
  };

  const toggleFolder = (folderId) => {
    setExpandedFolders(prev =>
      prev.includes(folderId)
        ? prev.filter(f => f !== folderId)
        : [...prev, folderId]
    );
  };

  const handleTerminalCommand = (cmd) => {
    const newLines = [...terminalLines, { type: 'input', text: `$ ${cmd}` }];
    const lowerCmd = cmd.trim().toLowerCase();

    if (lowerCmd === 'clear') {
      setTerminalLines([]);
      return;
    }

    let output;
    switch (lowerCmd) {
      case 'help':
        output = 'Available commands: help, clear, ls, pwd, npm run dev, npm run build, npm install';
        break;
      case 'ls':
        output = 'node_modules/  public/  src/  index.html  package.json  vite.config.js';
        break;
      case 'pwd':
        output = '/home/project';
        break;
      case 'npm run dev':
      case 'npm run dev -- --host':
        output = '\n  VITE v5.0.0  ready in 320 ms\n\n  ➜  Local:   http://localhost:5173/\n  ➜  Network: http://192.168.1.5:5173/\n  ➜  press h + enter to show help';
        break;
      case 'npm run build':
        output = 'vite v5.0.0 building for production...\n✓ 42 modules transformed.\ndist/index.html                  0.46 kB\ndist/assets/index-DiwrgTda.css   1.38 kB\ndist/assets/index-CdL__jS1.js   52.3 kB\n✓ built in 1.2s';
        break;
      case 'npm install':
      case 'npm i':
        output = 'added 287 packages in 4.2s\n\n62 packages are looking for funding\n  run `npm fund` for details';
        break;
      default:
        output = `bash: ${cmd}: command not found`;
    }

    newLines.push({ type: 'output', text: output });
    setTerminalLines(newLines);
  };

  const renderFolder = (folderId, folder, depth = 0) => {
    const isExpanded = expandedFolders.includes(folderId);
    return (
      <div key={folderId}>
        <button
          onClick={() => toggleFolder(folderId)}
          className="w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-sm hover:bg-white/[0.05] transition-colors text-gray-300"
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
        >
          {isExpanded
            ? <ChevronDown size={14} className="text-gray-500 flex-shrink-0" />
            : <ChevronRight size={14} className="text-gray-500 flex-shrink-0" />
          }
          <Folder size={14} className={isExpanded ? "text-violet-400 flex-shrink-0" : "text-gray-500 flex-shrink-0"} />
          <span className="text-xs font-medium">{folder.name}</span>
        </button>
        {isExpanded && (
          <div>
            {Object.entries(folder.folders).map(([childId, childFolder]) =>
              renderFolder(childId, childFolder, depth + 1)
            )}
            {folder.files.map(filePath => {
              const file = files[filePath];
              if (!file) return null;
              const isSelected = selectedFile === filePath;
              return (
                <button
                  key={filePath}
                  onClick={() => setSelectedFile(filePath)}
                  className={`w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-sm transition-all ${
                    isSelected
                      ? 'bg-violet-500/15 text-violet-300'
                      : 'text-gray-400 hover:bg-white/[0.05] hover:text-gray-300'
                  }`}
                  style={{ paddingLeft: `${(depth + 1) * 12 + 8}px` }}
                >
                  <File size={14} className={isSelected ? 'text-violet-400 flex-shrink-0' : 'text-gray-500 flex-shrink-0'} />
                  <span className="font-mono text-xs">{file.name}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  useEffect(() => {
    const fetchTestData = async () => {
      if (!testId || !user?.authToken) return;

      setIsLoading(true);

      try {
        const response = await fetch('http://localhost:8000/test-details', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            authToken: user.authToken,
            testId: testId
          })
        });

        const data = await response.json();

        if (response.ok && data.success) {
          setTestData(data.test);
          setPreviewHTML(`<div style="padding: 20px; color: #1e1e1e; font-family: sans-serif;">\n  <h1>Preview</h1>\n  <p>Your preview will appear here</p>\n</div>`);
          setChatMessages([
            { role: 'assistant', content: `Hello! I'm here to help you with "${data.test.name}".\n\nYou can ask me questions about the problem, request hints, or clarify requirements. I'll also provide code suggestions as you work through the solution.` }
          ]);
        } else if (data.detail === 'token_expired') {
          toast.error('Session Expired. Please Login again.');
          navigate('/login');
        } else {
          toast.error('Failed to load test details');
        }
      } catch (error) {
        console.error('Error fetching test data:', error);
        toast.error('Failed to load test details');
      } finally {
        setIsLoading(false);
      }
    };

    fetchTestData();
  }, [testId, user?.authToken, navigate]);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollTop = terminalEndRef.current.scrollHeight;
    }
  }, [terminalLines]);

  const handleAnswerChange = (questionId, answer) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: answer
    }));
  };

  const handleSubmitTest = async () => {
    if (!user?.authToken) return;

    setIsSubmitting(true);

    try {
      const response = await fetch('http://localhost:8000/submit-test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          authToken: user.authToken,
          testId: testId,
          answers: answers
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        toast.success('Test submitted successfully!');
        navigate('/');
      } else {
        toast.error(data.detail || 'Failed to submit test');
      }
    } catch (error) {
      console.error('Error submitting test:', error);
      toast.error('Failed to submit test');
    } finally {
      setIsSubmitting(false);
    }
  };

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

  const handleSendMessage = () => {
    if (!inputMessage.trim()) return;

    const newMessage = { role: 'user', content: inputMessage };
    setChatMessages(prev => [...prev, newMessage]);
    setInputMessage('');
    setIsTyping(true);

    setTimeout(() => {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: 'I understand. Let me help you with that. Here\'s a suggestion for your approach:\n\n1. First, break down the problem into smaller parts\n2. Consider the edge cases\n3. Start with a simple implementation\n\nWould you like me to provide more specific guidance on any of these steps?'
      }]);
      setIsTyping(false);
    }, 1500);
  };

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0b] text-gray-100 font-inter">
      {/* Header */}
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
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <Clock size={12} />
            <span className="text-xs font-medium">30:00</span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex overflow-hidden">
        {testData ? (
          <>
            {/* Left Panel - Chat Only */}
            <div className="flex-1 min-w-[350px] max-w-[500px] border-r border-white/[0.06] flex flex-col">
              <div className="px-4 py-3 border-b border-white/[0.06]">
                <div className="flex items-center gap-2">
                  <MessageSquare size={14} className="text-violet-400" />
                  <span className="text-sm font-semibold text-white">Chat</span>
                  <span className="ml-auto text-xs text-gray-500">AI Assistant</span>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto custom-scrollbar">
                <div className="p-4 space-y-4">
                  {/* Chat Messages */}
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
                        <div className={`inline-block px-4 py-2 rounded-2xl text-sm ${
                          msg.role === 'user'
                            ? 'bg-violet-500/10 border border-violet-500/20 text-gray-200'
                            : 'bg-white/[0.03] border border-white/[0.06] text-gray-300'
                        }`}>
                          {msg.content}
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

            {/* Problem Modal */}
            {showProblemModal && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={() => setShowProblemModal(false)}>
                <div className="bg-[#0a0a0b] rounded-2xl border border-white/[0.1] w-full max-w-3xl max-h-[80vh] flex flex-col shadow-2xl" onClick={e => e.stopPropagation()}>
                  <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center">
                        <Lightbulb size={20} className="text-violet-400" />
                      </div>
                      <h2 className="text-lg font-semibold text-white">Problem Statement</h2>
                    </div>
                    <button
                      onClick={() => setShowProblemModal(false)}
                      className="p-2 rounded-lg hover:bg-white/[0.05] transition-colors"
                    >
                      <X size={18} className="text-gray-400" />
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
                    <h3 className="text-xl font-semibold text-white mb-4">{testData.name}</h3>
                    <p className="text-sm leading-relaxed text-gray-400 mb-6">{testData.description}</p>

                    {testData.details && Array.isArray(testData.details) && testData.details.length > 0 && (
                      <div className="space-y-3">
                        <h4 className="text-sm font-semibold text-white mb-3">Requirements</h4>
                        {testData.details.map((item, index) => (
                          <div
                            key={index}
                            className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]"
                          >
                            <h5 className="font-semibold text-sm mb-2 text-violet-400">
                              {item.title}
                            </h5>
                            <div
                              className="text-sm leading-relaxed text-gray-400"
                              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(item.description) }}
                            />
                          </div>
                        ))}
                      </div>
                    )}

                    {testData.questions && testData.questions.length > 0 && (
                      <div className="space-y-3 mt-6">
                        <h4 className="text-sm font-semibold text-white mb-3">Questions</h4>
                        {testData.questions.map((question, index) => (
                          <div
                            key={question.id}
                            className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]"
                          >
                            <div className="flex items-start gap-3 mb-3">
                              <div className="w-7 h-7 rounded-lg bg-violet-500/15 flex items-center justify-center text-sm font-semibold text-violet-400 flex-shrink-0">
                                {index + 1}
                              </div>
                              <p className="text-sm font-medium text-white flex-1">
                                {question.question}
                              </p>
                              {answers[question.id] && (
                                <CheckCircle size={16} className="text-emerald-400 flex-shrink-0" />
                              )}
                            </div>
                            <div className="space-y-2 ml-10">
                              {question.options?.map((option, optIndex) => (
                                <label
                                  key={optIndex}
                                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all border text-sm ${
                                    answers[question.id] === option
                                      ? 'bg-violet-500/10 border-violet-500/30 text-violet-300'
                                      : 'bg-white/[0.02] border-white/[0.06] text-gray-400 hover:bg-white/[0.04]'
                                  }`}
                                >
                                  <input
                                    type="radio"
                                    name={`modal-question-${question.id}`}
                                    value={option}
                                    checked={answers[question.id] === option}
                                    onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                                    className="hidden"
                                  />
                                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                                    answers[question.id] === option
                                      ? 'border-violet-500'
                                      : 'border-gray-500'
                                  }`}>
                                    {answers[question.id] === option && (
                                      <div className="w-2 h-2 rounded-full bg-violet-500" />
                                    )}
                                  </div>
                                  <span>{option}</span>
                                </label>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="px-6 py-4 border-t border-white/[0.06] flex justify-end">
                    <button
                      onClick={() => setShowProblemModal(false)}
                      className="px-6 py-2.5 rounded-xl bg-violet-500 text-white text-sm font-medium hover:bg-violet-600 transition-colors"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Right Panel - Code Editor & Preview with Tabs */}
            <div className="flex-1 flex flex-col">
              {/* Tab Headers */}
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

              {/* Tab Content */}
              <div className="flex-1 overflow-hidden">
                {activeRightTab === 'code' && (
                  <div className="h-full flex flex-col">
                    {/* Editor + File Explorer Row */}
                    <div className={`flex-1 flex min-h-0 ${showTerminal ? '' : 'flex-1'}`}>
                      {/* File Explorer */}
                      <div className="w-60 border-r border-white/[0.06] flex flex-col bg-[#0d0d0e]">
                        <div className="px-3 py-2 border-b border-white/[0.06] flex items-center gap-2">
                          <Folder size={14} className="text-violet-400" />
                          <span className="text-xs font-medium text-gray-300">Explorer</span>
                        </div>
                        <div className="flex-1 overflow-y-auto custom-scrollbar py-2">
                          {renderFolder('root', folderTree.root, 0)}
                        </div>
                      </div>
                      {/* Monaco Editor */}
                      <div className="flex-1 min-w-0">
                        <Editor
                          height="100%"
                          language={files[selectedFile]?.language || 'javascript'}
                          theme="vs-dark"
                          value={files[selectedFile]?.content || ''}
                          onChange={(value) => {
                            setFiles(prev => ({
                              ...prev,
                              [selectedFile]: {
                                ...prev[selectedFile],
                                content: value
                              }
                            }));
                          }}
                          options={{
                            minimap: { enabled: false },
                            fontSize: 13,
                            fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
                            padding: { top: 12, bottom: 12 },
                            scrollBeyondLastLine: false,
                            lineNumbers: 'on',
                            lineNumbersMinChars: 3,
                            renderLineHighlight: 'line',
                            cursorBlinking: 'smooth',
                            cursorSmoothCaretAnimation: 'on',
                            smoothScrolling: true,
                            tabSize: 2,
                            wordWrap: 'on',
                            automaticLayout: true,
                            scrollbar: {
                              verticalScrollbarSize: 8,
                              horizontalScrollbarSize: 8
                            }
                          }}
                        />
                      </div>
                    </div>

                    {/* Terminal Panel */}
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
                                  'text-gray-300'
                                }`}>
                                  {line.type === 'input' ? line.text : line.text}
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
                            <div className="text-gray-500 italic">No output yet. Run your code to see output here.</div>
                          )}
                          {activeTerminalTab === 'problems' && (
                            <div className="text-emerald-400">No problems detected.</div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
                {activeRightTab === 'preview' && (
                  <div className="h-full overflow-auto bg-white">
                    <div dangerouslySetInnerHTML={{ __html: previewHTML }} />
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-500">
              <Zap size={32} className="mx-auto mb-3 text-gray-600" />
              <p className="text-sm">Test not found or failed to load</p>
            </div>
          </div>
        )}
      </main>

      {/* Footer Actions */}
      <footer className="px-4 py-3 border-t border-white/[0.06] bg-[#0a0a0b]/80 backdrop-blur-xl flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <CheckCircle size={14} />
            <span className="text-xs font-medium">{Object.keys(answers).length} answered</span>
          </div>
          <div className="text-xs text-gray-500">
            of {testData?.questions?.length || 0} questions
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 rounded-lg font-medium text-sm bg-white/[0.05] border border-white/[0.1] text-gray-400 hover:bg-white/[0.08] hover:text-gray-300 transition-all"
          >
            Cancel
          </button>
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
        </div>
      </footer>

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
};

export default TestPage;