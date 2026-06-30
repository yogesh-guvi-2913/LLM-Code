import { createContext, useContext, useState, useEffect, useRef, useCallback, useMemo } from 'react';
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

const getLanguageFromPath = (path) => {
  const ext = path.split('.').pop()?.toLowerCase();
  const languageMap = {
    'js': 'javascript', 'jsx': 'javascript', 'ts': 'typescript',
    'tsx': 'typescript', 'css': 'css', 'scss': 'scss',
    'html': 'html', 'json': 'json', 'md': 'markdown',
    'py': 'python', 'yaml': 'yaml', 'yml': 'yaml',
    'sh': 'shell', 'bash': 'shell', 'dockerfile': 'dockerfile',
  };
  if (ext === 'dockerfile' || path.toLowerCase().includes('dockerfile')) return 'dockerfile';
  if (path.endsWith('.worker_addon')) return 'json';
  return languageMap[ext] || 'plaintext';
};

const buildFolderTreeFromFiles = (files) => {
  const root = { id: 'root', name: 'project', folders: {}, files: [] };
  
  for (const filePath of Object.keys(files)) {
    const parts = filePath.split('/').filter(Boolean);
    if (parts.length === 0) continue;
    
    let current = root;
    let currentId = 'root';
    const fileName = parts[parts.length - 1];
    
    for (let i = 0; i < parts.length - 1; i++) {
      const folderName = parts[i];
      const folderId = `${currentId}/${folderName}`;
      
      if (!current.folders[folderId]) {
        current.folders[folderId] = { id: folderId, name: folderName, folders: {}, files: [] };
      }
      current = current.folders[folderId];
      currentId = folderId;
    }
    
    current.files.push(filePath);
  }
  
  return { root };
};

const convertProjectFilesToState = (projectFiles) => {
  const state = {};
  for (const [path, content] of Object.entries(projectFiles)) {
    if (typeof content !== 'string') continue;
    state[path] = {
      name: path.split('/').pop(),
      language: getLanguageFromPath(path),
      content,
    };
  }
  return state;
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
  const [activeRightTab, setActiveRightTab] = useState('preview');
  const [expandedFolders, setExpandedFolders] = useState(['root']);
  const [selectedFile, setSelectedFile] = useState(null);
  const [showTerminal, setShowTerminal] = useState(true);
  const [terminalLines, setTerminalLines] = useState([
    { type: 'system', text: 'Session starting...' }
  ]);
  const [terminalInput, setTerminalInput] = useState('');
  const [activeTerminalTab, setActiveTerminalTab] = useState('terminal');
  const [files, setFiles] = useState({});
  const [consoleLogs, setConsoleLogs] = useState([]);
  const [previewErrors, setPreviewErrors] = useState([]);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [sessionStatus, setSessionStatus] = useState('idle');
  const terminalEndRef = useRef(null);
  const timeLeftRef = useRef(testData?.duration || 1800);

  const folderTree = useMemo(() => buildFolderTreeFromFiles(files), [files]);

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
        output = 'frontend/  backend/  docker-compose.yml';
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
          newFiles[path] = {
            name: path.split('/').pop(),
            language: getLanguageFromPath(path),
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
    sessionId: sessionInfo?.sessionId,
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

          if (data.test.projectFiles && Object.keys(data.test.projectFiles).length > 0) {
            const convertedFiles = convertProjectFilesToState(data.test.projectFiles);
            setFiles(convertedFiles);
            
            const firstFile = Object.keys(convertedFiles)[0];
            if (firstFile) {
              setSelectedFile(firstFile);
            }

            const allFolderPaths = ['root'];
            for (const path of Object.keys(convertedFiles)) {
              const parts = path.split('/').filter(Boolean);
              let currentPath = 'root';
              for (let i = 0; i < parts.length - 1; i++) {
                currentPath = `${currentPath}/${parts[i]}`;
                if (!allFolderPaths.includes(currentPath)) {
                  allFolderPaths.push(currentPath);
                }
              }
            }
            setExpandedFolders(allFolderPaths);
          }

          timeLeftRef.current = data.test.duration || 1800;

          setSessionStatus('starting');
          setTerminalLines(prev => [...prev, { type: 'system', text: 'Starting Docker containers...' }]);

          try {
            const sessionRes = await fetch('http://localhost:8000/session/start', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ authToken, testId })
            });
            const sessionData = await sessionRes.json();

            if (sessionData.success && sessionData.session) {
              setSessionInfo(sessionData.session);
              setSessionStatus('ready');
              setTerminalLines(prev => [...prev, {
                type: 'system',
                text: `Containers ready! Preview: ${sessionData.session.frontendUrl}`
              }]);
            } else {
              setSessionStatus('error');
              setTerminalLines(prev => [...prev, {
                type: 'error',
                text: `Failed to start containers: ${sessionData.detail || 'Unknown error'}`
              }]);
            }
          } catch (sessionErr) {
            setSessionStatus('error');
            setTerminalLines(prev => [...prev, {
              type: 'error',
              text: `Session start error: ${sessionErr.message}`
            }]);
          }
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
    return () => {
      if (sessionInfo?.sessionId && authToken) {
        fetch('http://localhost:8000/session/stop', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ authToken, sessionId: sessionInfo.sessionId })
        }).catch(() => {});
      }
    };
  }, [sessionInfo?.sessionId, authToken]);

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
    sessionInfo,
    sessionStatus,
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