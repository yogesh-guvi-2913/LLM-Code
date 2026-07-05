import React, { useState, useEffect } from 'react';

const FileBrowser = ({ sessionId, apiBaseUrl, onFileSelect, onFileCreate, onFileDelete }) => {
  const [files, setFiles] = useState([]);
  const [currentPath, setCurrentPath] = useState('/');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [newFileName, setNewFileName] = useState('');
  const [showNewFile, setShowNewFile] = useState(false);
  
  const baseUrl = apiBaseUrl || 'http://localhost:8090';
  
  const fetchFiles = async (path = currentPath) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `${baseUrl}/v1/sessions/${sessionId}/files?path=${encodeURIComponent(path)}`
      );
      
      if (!response.ok) {
        throw new Error(`Failed to fetch files: ${response.statusText}`);
      }
      
      const data = await response.json();
      setFiles(data.files || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch files');
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    fetchFiles();
  }, [sessionId, currentPath]);
  
  const handleFileClick = async (file) => {
    if (file.type === 'directory') {
      setCurrentPath(file.path);
      return;
    }
    
    try {
      const response = await fetch(
        `${baseUrl}/v1/sessions/${sessionId}/files/${encodeURIComponent(file.path)}`
      );
      
      if (!response.ok) {
        throw new Error('Failed to fetch file content');
      }
      
      const content = await response.text();
      onFileSelect?.(file.path, content);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch file');
    }
  };
  
  const handleCreateFile = async () => {
    if (!newFileName.trim()) return;
    
    const filePath = currentPath === '/' 
      ? `/${newFileName}` 
      : `${currentPath}/${newFileName}`;
    
    try {
      const response = await fetch(
        `${baseUrl}/v1/sessions/${sessionId}/files/${encodeURIComponent(filePath)}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: '' })
        }
      );
      
      if (!response.ok) {
        throw new Error('Failed to create file');
      }
      
      setNewFileName('');
      setShowNewFile(false);
      fetchFiles();
      onFileCreate?.(filePath);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create file');
    }
  };
  
  const handleDeleteFile = async (file) => {
    if (!confirm(`Delete ${file.name}?`)) return;
    
    try {
      const response = await fetch(
        `${baseUrl}/v1/sessions/${sessionId}/files/${encodeURIComponent(file.path)}`,
        { method: 'DELETE' }
      );
      
      if (!response.ok) {
        throw new Error('Failed to delete file');
      }
      
      fetchFiles();
      onFileDelete?.(file.path);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete file');
    }
  };
  
  const handleNavigateUp = () => {
    const parentPath = currentPath.split('/').slice(0, -1).join('/') || '/';
    setCurrentPath(parentPath);
  };
  
  return (
    <div className="flex flex-col h-full bg-white border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <button
            onClick={handleNavigateUp}
            disabled={currentPath === '/'}
            className="p-1 hover:bg-gray-200 rounded disabled:opacity-50"
          >
            ←
          </button>
          <span className="text-sm font-mono text-gray-700">{currentPath}</span>
        </div>
        
        <button
          onClick={() => setShowNewFile(true)}
          className="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded"
        >
          New File
        </button>
      </div>
      
      {showNewFile && (
        <div className="px-4 py-2 bg-gray-50 border-b border-gray-200">
          <div className="flex items-center space-x-2">
            <input
              type="text"
              value={newFileName}
              onChange={(e) => setNewFileName(e.target.value)}
              placeholder="filename.ext"
              className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded"
            />
            <button
              onClick={handleCreateFile}
              className="px-3 py-1 text-sm bg-green-600 hover:bg-green-500 text-white rounded"
            >
              Create
            </button>
            <button
              onClick={() => setShowNewFile(false)}
              className="px-3 py-1 text-sm bg-gray-600 hover:bg-gray-500 text-white rounded"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      
      {error && (
        <div className="px-4 py-2 bg-red-100 text-red-700 text-sm border-b border-red-200">
          {error}
        </div>
      )}
      
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
          </div>
        ) : files.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            Empty directory
          </div>
        ) : (
          <ul className="divide-y divide-gray-200">
            {files.map((file) => (
              <li
                key={file.path}
                className="flex items-center justify-between px-4 py-2 hover:bg-gray-50 cursor-pointer"
                onClick={() => handleFileClick(file)}
              >
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-700">{file.name}</span>
                </div>
                
                <div className="flex items-center space-x-4">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteFile(file);
                    }}
                    className="p-1 hover:bg-red-100 rounded text-red-600"
                  >
                    🗑️
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default FileBrowser;