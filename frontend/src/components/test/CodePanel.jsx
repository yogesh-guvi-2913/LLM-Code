import Editor from '@monaco-editor/react';
import FileExplorer from './FileExplorer';
import TerminalPanel from './TerminalPanel';
import { useTest } from '../../contexts/TestContext';
import { Lock } from 'lucide-react';

function CodePanel() {
  const { files, selectedFile, updateFile, testData } = useTest();

  const currentFile = files[selectedFile];
  const isReadOnly = testData?.codeEdit !== 1;

  const handleEditorChange = (value) => {
    if (value !== undefined && !isReadOnly) {
      updateFile(selectedFile, value);
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 flex min-h-0">
        <FileExplorer />
        <div className="flex-1 min-w-0 relative">
          {isReadOnly && (
            <div className="absolute top-2 right-3 z-10 flex items-center gap-1.5 px-2 py-1 rounded-md bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs font-medium pointer-events-none">
              <Lock size={11} />
              <span>Read-only · AI generates code</span>
            </div>
          )}
          <Editor
            height="100%"
            language={currentFile?.language || 'javascript'}
            theme="vs-dark"
            value={currentFile?.content || ''}
            onChange={handleEditorChange}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
              padding: { top: 12, bottom: 12 },
              scrollBeyondLastLine: false,
              lineNumbers: 'on',
              lineNumbersMinChars: 3,
              renderLineHighlight: 'line',
              cursorBlinking: 'smooth',
              cursorSmoothCaretAnimation: 'on',
              smoothScrolling: true,
              tabSize: 2,
              wordWrap: 'on',
              automaticLayout: true,
              readOnly: isReadOnly,
              domReadOnly: isReadOnly,
              scrollbar: {
                verticalScrollbarSize: 8,
                horizontalScrollbarSize: 8
              }
            }}
          />
        </div>
      </div>
      <TerminalPanel />
    </div>
  );
}

export default CodePanel;
