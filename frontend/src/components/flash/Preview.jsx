import React, { useState, useEffect } from 'react';

const Preview = ({ sessionId, previewUrl, onClose }) => {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    const fetchPreviewUrl = async () => {
      try {
        const response = await fetch(
          `http://localhost:8090/v1/sessions/${sessionId}/preview`
        );
        
        if (!response.ok) {
          throw new Error('Failed to get preview URL');
        }
        
        const data = await response.json();
        setUrl(data.url);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load preview');
      } finally {
        setLoading(false);
      }
    };
    
    if (!previewUrl) {
      fetchPreviewUrl();
    } else {
      setUrl(previewUrl);
      setLoading(false);
    }
  }, [sessionId, previewUrl]);
  
  const handleRefresh = () => {
    setLoading(true);
    const iframe = document.querySelector('iframe');
    if (iframe) {
      iframe.src = url;
    }
  };
  
  const handleOpenExternal = () => {
    window.open(url, '_blank');
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-gray-50">
        <p className="text-red-600">{error}</p>
      </div>
    );
  }
  
  return (
    <div className="flex flex-col h-full bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium text-gray-700">Preview</span>
          <span className="text-xs text-gray-500 font-mono truncate max-w-xs">{url}</span>
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={handleRefresh}
            className="p-1 hover:bg-gray-200 rounded"
            title="Refresh"
          >
            🔄
          </button>
          <button
            onClick={handleOpenExternal}
            className="p-1 hover:bg-gray-200 rounded"
            title="Open in new tab"
          >
            🔗
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-200 rounded"
              title="Close preview"
            >
              ✕
            </button>
          )}
        </div>
      </div>
      
      <div className="flex-1">
        <iframe
          src={url}
          className="w-full h-full border-0"
          title="Preview"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        />
      </div>
    </div>
  );
};

export default Preview;