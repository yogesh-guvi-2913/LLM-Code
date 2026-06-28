import { useEffect } from 'react';

export function useConsoleCapture(onLog, onError) {
  useEffect(() => {
    const handleMessage = (event) => {
      if (!event.data) return;

      if (event.data.type === 'console' && onLog) {
        onLog({
          level: event.data.level,
          message: event.data.message
        });
      }

      if (event.data.type === 'preview-error' && onError) {
        onError({
          message: event.data.message
        });
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [onLog, onError]);
}

export default useConsoleCapture;