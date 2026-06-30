import { useState, useRef, useEffect } from 'react';
import { useTest } from '../../contexts/TestContext';
import { Maximize2, RefreshCw, Smartphone, Monitor, Loader2, AlertCircle } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function PreviewFrame() {
  const { sessionInfo, sessionStatus } = useTest();
  const [viewport, setViewport] = useState('desktop');
  const [iframeKey, setIframeKey] = useState(0);
  const iframeRef = useRef(null);

  const handleRefresh = () => {
    setIframeKey(prev => prev + 1);
  };

  const handleExpand = () => {
    if (sessionInfo?.frontendUrl) {
      window.open(`${API_BASE_URL}${sessionInfo.frontendUrl}`, '_blank');
    }
  };

  if (sessionStatus === 'starting' || sessionStatus === 'idle') {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-gray-50">
        <Loader2 className="animate-spin mb-3 text-violet-500" size={28} />
        <p className="text-sm text-gray-600 font-medium">Starting containers...</p>
        <p className="text-xs text-gray-400 mt-1">Spinning up frontend, backend & database</p>
      </div>
    );
  }

  if (sessionStatus === 'error' || !sessionInfo) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-gray-50">
        <AlertCircle className="mb-3 text-red-400" size={28} />
        <p className="text-sm text-red-500 font-medium">Failed to start preview</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-3 px-3 py-1.5 text-xs bg-violet-500 text-white rounded-lg hover:bg-violet-600 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  const previewUrl = `${API_BASE_URL}${sessionInfo.frontendUrl}`;
  const viewportWidth = viewport === 'mobile' ? '375px' : '100%';

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setViewport('desktop')}
            className={`p-1.5 rounded ${viewport === 'desktop' ? 'bg-gray-200 text-gray-700' : 'text-gray-400 hover:text-gray-600'}`}
            title="Desktop view"
          >
            <Monitor size={14} />
          </button>
          <button
            onClick={() => setViewport('mobile')}
            className={`p-1.5 rounded ${viewport === 'mobile' ? 'bg-gray-200 text-gray-700' : 'text-gray-400 hover:text-gray-600'}`}
            title="Mobile view"
          >
            <Smartphone size={14} />
          </button>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-gray-400">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Live</span>
          </div>
          <button
            onClick={handleRefresh}
            className="p-1.5 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition-colors"
            title="Refresh preview"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={handleExpand}
            className="p-1.5 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition-colors"
            title="Open in new tab"
          >
            <Maximize2 size={14} />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-hidden flex justify-center bg-gray-100">
        <div
          style={{ width: viewportWidth, maxWidth: '100%' }}
          className="h-full bg-white transition-all duration-200 shadow-sm"
        >
          <iframe
            key={iframeKey}
            ref={iframeRef}
            src={previewUrl}
            title="preview"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
            className="w-full h-full border-0"
          />
        </div>
      </div>
    </div>
  );
}

export default PreviewFrame;
