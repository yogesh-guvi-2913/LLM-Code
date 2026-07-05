import React, { useEffect, useRef, useState } from 'react';
import { Terminal as XTerminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';

const Terminal = ({ sessionId, wsUrl, onClose }) => {
  const terminalRef = useRef(null);
  const xtermRef = useRef(null);
  const wsRef = useRef(null);
  const fitAddonRef = useRef(null);
  
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    if (!terminalRef.current) return;
    
    const xterm = new XTerminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Monaco, Menlo, "Courier New", monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#d4d4d4',
        selectionBackground: '#264f78',
        black: '#000000',
        red: '#cd3131',
        green: '#0dbc79',
        yellow: '#e5e510',
        blue: '#2472c8',
        magenta: '#bc3fbc',
        cyan: '#11a8cd',
        white: '#e5e5e5',
        brightBlack: '#666666',
        brightRed: '#f14c4c',
        brightGreen: '#23d18b',
        brightYellow: '#f5f543',
        brightBlue: '#3b8eea',
        brightMagenta: '#d670d6',
        brightCyan: '#29b8db',
        brightWhite: '#e5e5e5'
      }
    });
    
    const fitAddon = new FitAddon();
    xterm.loadAddon(fitAddon);
    xterm.open(terminalRef.current);
    
    fitAddon.fit();
    xtermRef.current = xterm;
    fitAddonRef.current = fitAddon;
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = wsUrl || `${protocol}//${window.location.hostname}:8090`;
    const ws = new WebSocket(`${host}/v1/sessions/${sessionId}/terminal`);
    
    ws.binaryType = 'arraybuffer';
    
    ws.onopen = () => {
      setConnected(true);
      setError(null);
      xterm.writeln('\x1b[32mConnected to sandbox terminal\x1b[0m');
    };
    
    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        const data = new Uint8Array(event.data);
        xterm.writeUtf8(data);
      } else {
        xterm.write(event.data);
      }
    };
    
    ws.onerror = (event) => {
      setError('WebSocket error');
      xterm.writeln('\x1b[31mConnection error\x1b[0m');
    };
    
    ws.onclose = (event) => {
      setConnected(false);
      if (event.code !== 1000) {
        xterm.writeln('\x1b[31mConnection closed\x1b[0m');
      }
    };
    
    wsRef.current = ws;
    
    xterm.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data));
      }
    });
    
    const handleResize = () => {
      if (fitAddonRef.current && xtermRef.current) {
        fitAddonRef.current.fit();
        
        const dimensions = {
          cols: xtermRef.current.cols,
          rows: xtermRef.current.rows
        };
        
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: 'resize',
            dimensions
          }));
        }
      }
    };
    
    window.addEventListener('resize', handleResize);
    
    return () => {
      window.removeEventListener('resize', handleResize);
      ws.close();
      xterm.dispose();
    };
  }, [sessionId, wsUrl]);
  
  const handleClear = () => {
    if (xtermRef.current) {
      xtermRef.current.clear();
    }
  };
  
  const handleDisconnect = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    onClose?.();
  };
  
  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium text-gray-200">Terminal</span>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={handleClear}
            className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 rounded"
          >
            Clear
          </button>
          <button
            onClick={handleDisconnect}
            className="px-3 py-1 text-xs bg-red-600 hover:bg-red-500 text-white rounded"
          >
            Disconnect
          </button>
        </div>
      </div>
      
      <div ref={terminalRef} className="flex-1 p-2" />
      
      {error && (
        <div className="px-4 py-2 bg-red-900 text-red-200 text-sm">
          Error: {error}
        </div>
      )}
    </div>
  );
};

export default Terminal;