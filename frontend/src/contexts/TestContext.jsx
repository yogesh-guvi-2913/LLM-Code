import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import toast from 'react-hot-toast';
import { useAIChat } from '../hooks/useAIChat';

const TestContext = createContext(null);

const stripCodeBlocks = (text) => {
  return text
    .replace(/```(?:file|delete):[^\n]+\n[\s\S]*?```/g, '')
    .replace(/```(?:file|delete):[^\n]+```/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
};

const DEFAULT_FILES = {
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
};

const FOLDER_TREE = {
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

export function TestProvider({ testId, authToken, navigate, children }) {
  const [testData, setTestData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [answers, setAnswers] = useState({});
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
  const [files, setFiles] = useState(DEFAULT_FILES);
  const [consoleLogs, setConsoleLogs] = useState([]);
  const [previewErrors, setPreviewErrors] = useState([]);
  const terminalEndRef = useRef(null);
  const timeLeftRef = useRef(testData?.duration || 1800);

  const folderTree = FOLDER_TREE;

  const toggleFolder = useCallback((folderId) => {
    setExpandedFolders(prev =>
      prev.includes(folderId)
        ? prev.filter(f => f !== folderId)
        : [...prev, folderId]
    );
  }, []);

  const handleTerminalCommand = useCallback((cmd) => {
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
  }, [terminalLines]);

  const handleAnswerChange = useCallback((questionId, answer) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: answer
    }));
  }, []);

  const handleSubmitTest = useCallback(async () => {
    if (!authToken) return;

    setIsSubmitting(true);

    try {
      const response = await fetch('http://localhost:8000/submit-test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          authToken: authToken,
          testId: testId,
          answers: answers,
          files: files,
          chatHistory: chatMessages.filter(m => !m.streaming).map(m => ({
            role: m.role,
            content: m.content
          }))
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        toast.success('Test submitted! Evaluating...');
        navigate(`/results/${testId}`);
      } else {
        toast.error(data.detail || 'Failed to submit test');
      }
    } catch (error) {
      console.error('Error submitting test:', error);
      toast.error('Failed to submit test');
    } finally {
      setIsSubmitting(false);
    }
  }, [authToken, testId, answers, files, chatMessages, navigate]);

  const handleCodeChanges = useCallback((changes) => {
    if (!Array.isArray(changes)) return;
    setFiles(prev => {
      const newFiles = { ...prev };
      for (const change of changes) {
        const { path, content, action = 'update' } = change;
        if (action === 'delete') {
          delete newFiles[path];
        } else {
          const ext = path.split('.').pop()?.toLowerCase();
          const languageMap = {
            'js': 'javascript', 'jsx': 'javascript', 'ts': 'typescript',
            'tsx': 'typescript', 'css': 'css', 'html': 'html', 'json': 'json'
          };
          newFiles[path] = {
            name: path.split('/').pop(),
            language: languageMap[ext] || 'plaintext',
            content
          };
        }
      }
      return newFiles;
    });
  }, []);

  const handleAIError = useCallback((error) => {
    toast.error(`AI error: ${error}`);
  }, []);

  const { sendMessage: wsSendMessage, isConnected: wsConnected } = useAIChat({
    testId,
    authToken,
    onCodeChanges: handleCodeChanges,
    onError: handleAIError
  });

  const handleSendMessage = useCallback(() => {
    if (!inputMessage.trim() || isTyping) return;

    const userMessage = inputMessage.trim();
    setChatMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setInputMessage('');
    setIsTyping(true);

    wsSendMessage({
      message: userMessage,
      currentFiles: files,
      onText: (text) => {
        setChatMessages(prev => {
          const last = prev[prev.length - 1];
          if (last && last.role === 'assistant' && last.streaming) {
            const rawContent = last.rawContent + text;
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...last,
              rawContent,
              content: stripCodeBlocks(rawContent)
            };
            return updated;
          }
          return [...prev, {
            role: 'assistant',
            rawContent: text,
            content: stripCodeBlocks(text) || 'Working on it...',
            streaming: true
          }];
        });
      },
      onDone: () => {
        setChatMessages(prev => {
          const last = prev[prev.length - 1];
          if (last && last.role === 'assistant' && last.streaming) {
            const cleanContent = stripCodeBlocks(last.rawContent || last.content);
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...last,
              streaming: false,
              content: cleanContent || 'Done! Code has been applied to your files.'
            };
            delete updated[updated.length - 1].rawContent;
            return updated;
          }
          return prev;
        });
        setIsTyping(false);
      },
      onError: (error) => {
        setChatMessages(prev => [...prev, {
          role: 'assistant',
          content: `Sorry, I encountered an error: ${error}`,
          streaming: false
        }]);
        setIsTyping(false);
      }
    });
  }, [inputMessage, isTyping, files, wsSendMessage]);

  const updateFile = useCallback((path, content) => {
    setFiles(prev => ({
      ...prev,
      [path]: {
        ...prev[path],
        content
      }
    }));
  }, []);

  const updateFiles = useCallback((newFiles) => {
    setFiles(prev => ({ ...prev, ...newFiles }));
  }, []);

  const addConsoleLog = useCallback((log) => {
    setConsoleLogs(prev => [...prev, { ...log, timestamp: Date.now() }]);
  }, []);

  const addPreviewError = useCallback((error) => {
    setPreviewErrors(prev => [...prev, { ...error, timestamp: Date.now() }]);
  }, []);

  const clearConsoleLogs = useCallback(() => {
    setConsoleLogs([]);
  }, []);

  const clearPreviewErrors = useCallback(() => {
    setPreviewErrors([]);
  }, []);

  useEffect(() => {
    const fetchTestData = async () => {
      if (!testId || !authToken) return;

      setIsLoading(true);

      try {
        const response = await fetch('http://localhost:8000/test-details', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            authToken: authToken,
            testId: testId
          })
        });

        const data = await response.json();

        if (response.ok && data.success) {
          setTestData(data.test);
          setChatMessages([
            { role: 'assistant', content: `Hello! I'm here to help you with "${data.test.name}".\n\nYou can ask me questions about the problem, request hints, or clarify requirements. I'll also provide code suggestions as you work through the solution.` }
          ]);
          if (data.test.initialFiles) {
            setFiles(prev => ({ ...prev, ...data.test.initialFiles }));
          }
          timeLeftRef.current = data.test.duration || 1800;
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
  }, [testId, authToken, navigate]);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollTop = terminalEndRef.current.scrollHeight;
    }
  }, [terminalLines]);

  const value = {
    testData,
    isLoading,
    isSubmitting,
    answers,
    handleAnswerChange,
    handleSubmitTest,
    chatMessages,
    inputMessage,
    setInputMessage,
    isTyping,
    handleSendMessage,
    showProblemModal,
    setShowProblemModal,
    activeRightTab,
    setActiveRightTab,
    expandedFolders,
    toggleFolder,
    folderTree,
    selectedFile,
    setSelectedFile,
    files,
    setFiles,
    updateFile,
    updateFiles,
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
    addConsoleLog,
    clearConsoleLogs,
    previewErrors,
    addPreviewError,
    clearPreviewErrors,
    wsConnected,
  };

  return (
    <TestContext.Provider value={value}>
      {children}
    </TestContext.Provider>
  );
}

export function useTest() {
  const context = useContext(TestContext);
  if (!context) {
    throw new Error('useTest must be used within a TestProvider');
  }
  return context;
}

export default TestContext;
