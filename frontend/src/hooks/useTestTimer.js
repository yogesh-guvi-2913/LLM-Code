import { useState, useEffect, useRef, useCallback } from 'react';

export function useTestTimer(durationSeconds, onExpire) {
  const [timeLeft, setTimeLeft] = useState(durationSeconds || 1800);
  const [isExpired, setIsExpired] = useState(false);
  const onExpireRef = useRef(onExpire);
  const hasExpiredRef = useRef(false);

  useEffect(() => {
    onExpireRef.current = onExpire;
  }, [onExpire]);

  useEffect(() => {
    setTimeLeft(durationSeconds || 1800);
    setIsExpired(false);
    hasExpiredRef.current = false;
  }, [durationSeconds]);

  useEffect(() => {
    const interval = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1 && !hasExpiredRef.current) {
          hasExpiredRef.current = true;
          clearInterval(interval);
          setIsExpired(true);
          if (onExpireRef.current) {
            onExpireRef.current();
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const formatTime = useCallback((seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${String(secs).padStart(2, '0')}`;
  }, []);

  const isLowTime = timeLeft <= 300;
  const isCritical = timeLeft <= 60;

  return {
    timeLeft,
    formattedTime: formatTime(timeLeft),
    isExpired,
    isLowTime,
    isCritical
  };
}

export default useTestTimer;
