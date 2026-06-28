import { File, Folder, ChevronRight, ChevronDown } from 'lucide-react';
import { useTest } from '../../contexts/TestContext';

function FileExplorer() {
  const {
    expandedFolders,
    toggleFolder,
    folderTree,
    selectedFile,
    setSelectedFile,
    files
  } = useTest();

  const renderFolder = (folderId, folder, depth = 0) => {
    const isExpanded = expandedFolders.includes(folderId);
    return (
      <div key={folderId}>
        <button
          onClick={() => toggleFolder(folderId)}
          className="w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-sm hover:bg-white/[0.05] transition-colors text-gray-300"
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
        >
          {isExpanded
            ? <ChevronDown size={14} className="text-gray-500 flex-shrink-0" />
            : <ChevronRight size={14} className="text-gray-500 flex-shrink-0" />
          }
          <Folder size={14} className={isExpanded ? "text-violet-400 flex-shrink-0" : "text-gray-500 flex-shrink-0"} />
          <span className="text-xs font-medium">{folder.name}</span>
        </button>
        {isExpanded && (
          <div>
            {Object.entries(folder.folders).map(([childId, childFolder]) =>
              renderFolder(childId, childFolder, depth + 1)
            )}
            {folder.files.map(filePath => {
              const file = files[filePath];
              if (!file) return null;
              const isSelected = selectedFile === filePath;
              return (
                <button
                  key={filePath}
                  onClick={() => setSelectedFile(filePath)}
                  className={`w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-sm transition-all ${
                    isSelected
                      ? 'bg-violet-500/15 text-violet-300'
                      : 'text-gray-400 hover:bg-white/[0.05] hover:text-gray-300'
                  }`}
                  style={{ paddingLeft: `${(depth + 1) * 12 + 8}px` }}
                >
                  <File size={14} className={isSelected ? 'text-violet-400 flex-shrink-0' : 'text-gray-500 flex-shrink-0'} />
                  <span className="font-mono text-xs">{file.name}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="w-60 border-r border-white/[0.06] flex flex-col bg-[#0d0d0e]">
      <div className="px-3 py-2 border-b border-white/[0.06] flex items-center gap-2">
        <Folder size={14} className="text-violet-400" />
        <span className="text-xs font-medium text-gray-300">Explorer</span>
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar py-2">
        {renderFolder('root', folderTree.root, 0)}
      </div>
    </div>
  );
}

export default FileExplorer;
