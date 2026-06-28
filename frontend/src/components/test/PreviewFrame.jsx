import { useCallback, useMemo, useRef, useEffect, useState } from 'react';
import { buildPreviewHTML } from '../../utils/previewBuilder';
import { useTest } from '../../contexts/TestContext';
import { useConsoleCapture } from '../../hooks/useConsoleCapture';
import { Maximize2, RefreshCw, Smartphone, Monitor } from 'lucide-react';

function PreviewFrame() {
  const { files, addConsoleLog, addPreviewError, clearConsoleLogs, clearPreviewErrors } = useTest();
  const [iframeKey, setIframeKey] = useState(0);
  const [viewport, setViewport] = useState('desktop');
  const [isReady, setIsReady] = useState(false);
  const debounceTimer = useRef(null);

  const onLog = useCallback((log) => {
    addConsoleLog(log);
  }, [addConsoleLog]);

  const onError = useCallback((error) => {
    addPreviewError(error);
  }, [addPreviewError]);

  useConsoleCapture(onLog, onError);

  const html = useMemo(() => {
    try {
      return buildPreviewHTML(files);
    } catch (err) {
      console.error('Preview build error:', err);
      return `<html><body style="padding:20px;color:#f48771;font-family:monospace;"><h3>Preview Build Error</h3><pre>${err.message}</pre></body></html>`;
    }
  }, [files]);

  useEffect(() => {
    clearConsoleLogs();
    clearPreviewErrors();
    setIsReady(false);

    if (debounceTimer.current) clearTimeout(debounceTimer.current);

    debounceTimer.current = setTimeout(() => {
      setIframeKey(prev => prev + 1);
      setIsReady(true);
    }, 300);

    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [html, clearConsoleLogs, clearPreviewErrors]);

  const handleRefresh = () => {
    clearConsoleLogs();
    clearPreviewErrors();
    setIframeKey(prev => prev + 1);
  };

  const handleExpand = () => {
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  };

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
        <div className="flex items-center gap-1">
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
          {!isReady ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              <RefreshCw size={16} className="animate-spin mr-2" />
              <span className="text-xs">Building preview...</span>
            </div>
          ) : (
            <iframe
              key={iframeKey}
              srcDoc={html}
              title="preview"
              sandbox="allow-scripts"
              className="w-full h-full border-0"
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default PreviewFrame;