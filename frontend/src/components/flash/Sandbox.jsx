import React, { useState, useEffect } from 'react';
import Terminal from './Terminal';
import FileBrowser from './FileBrowser';
import Preview from './Preview';
import TestRunner from './TestRunner';

const Sandbox = ({ testId, authToken, flashApiUrl, backendApiUrl }) => {
  const [sessionId, setSessionId] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [activeTab, setActiveTab] = useState('editor');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const flashUrl = flashApiUrl || 'http://localhost:8090';
  const backendUrl = backendApiUrl || '';
  
  useEffect(() => {
    initializeSession();
  }, [testId]);
  
  const initializeSession = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${backendUrl}/flash/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          testId,
          authToken
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to start session');
      }
      
      const data = await response.json();
      setSessionId(data.flashSessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initialize');
    } finally {
      setLoading(false);
    }
  };
  
  const handleFileSelect = (path, content) => {
    setSelectedFile(path);
    setFileContent(content);
    setActiveTab('editor');
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <p className="text-red-600">{error}</p>
          <button
            onClick={initializeSession}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }
  
  if (!sessionId) {
    return null;
  }
  
  return (
    <div className="flex flex-col h-screen bg-gray-100">
      <div className="px-4 py-3 bg-white border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900">Sandbox Environment</h1>
          <div className="text-sm text-gray-500">Session: {sessionId}</div>
        </div>
      </div>
      
      <div className="flex flex-1 overflow-hidden">
        <div className="w-64 border-r border-gray-200 overflow-hidden">
          <FileBrowser
            sessionId={sessionId}
            apiBaseUrl={flashUrl}
            onFileSelect={handleFileSelect}
          />
        </div>
        
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex border-b border-gray-200 bg-white">
            <button
              onClick={() => setActiveTab('editor')}
              className={`px-4 py-2 text-sm font-medium ${
                activeTab === 'editor'
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Editor
            </button>
            <button
              onClick={() => setActiveTab('preview')}
              className={`px-4 py-2 text-sm font-medium ${
                activeTab === 'preview'
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Preview
            </button>
          </div>
          
          <div className="flex-1 overflow-hidden">
            {activeTab === 'editor' ? (
              <div className="flex flex-col h-full">
                <div className="px-4 py-2 bg-gray-50 border-b border-gray-200">
                  <span className="text-sm font-mono text-gray-700">{selectedFile || 'No file selected'}</span>
                </div>
                <textarea
                  className="flex-1 p-4 font-mono text-sm bg-white resize-none focus:outline-none"
                  value={fileContent}
                  onChange={(e) => setFileContent(e.target.value)}
                  placeholder="Select a file to edit"
                  spellCheck={false}
                />
              </div>
            ) : (
              <Preview sessionId={sessionId} />
            )}
          </div>
        </div>
        
        <div className="w-80 border-l border-gray-200 overflow-y-auto p-4">
          <TestRunner
            testId={testId}
            authToken={authToken}
          />
        </div>
      </div>
      
      <div className="h-64 border-t border-gray-200">
        <Terminal sessionId={sessionId} wsUrl={flashUrl} />
      </div>
    </div>
  );
};

export default Sandbox;