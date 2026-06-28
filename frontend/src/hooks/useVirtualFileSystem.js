import { useCallback } from 'react';

export function useVirtualFileSystem(files, setFiles) {
  const updateFile = useCallback((path, content) => {
    setFiles(prev => {
      if (!prev[path]) {
        const language = getLanguageFromPath(path);
        return {
          ...prev,
          [path]: {
            name: path.split('/').pop(),
            language,
            content
          }
        };
      }
      return {
        ...prev,
        [path]: {
          ...prev[path],
          content
        }
      };
    });
  }, [setFiles]);

  const deleteFile = useCallback((path) => {
    setFiles(prev => {
      const newFiles = { ...prev };
      delete newFiles[path];
      return newFiles;
    });
  }, [setFiles]);

  const renameFile = useCallback((oldPath, newPath) => {
    setFiles(prev => {
      const file = prev[oldPath];
      if (!file) return prev;
      const newFiles = { ...prev };
      delete newFiles[oldPath];
      newFiles[newPath] = {
        ...file,
        name: newPath.split('/').pop(),
        language: getLanguageFromPath(newPath)
      };
      return newFiles;
    });
  }, [setFiles]);

  const createFile = useCallback((path, content = '') => {
    const language = getLanguageFromPath(path);
    setFiles(prev => ({
      ...prev,
      [path]: {
        name: path.split('/').pop(),
        language,
        content
      }
    }));
  }, [setFiles]);

  const getFile = useCallback((path) => {
    return files[path] || null;
  }, [files]);

  const getFileContent = useCallback((path) => {
    return files[path]?.content || '';
  }, [files]);

  const fileExists = useCallback((path) => {
    return path in files;
  }, [files]);

  const applyAICodeChanges = useCallback((changes) => {
    if (!Array.isArray(changes)) return;
    
    setFiles(prev => {
      const newFiles = { ...prev };
      
      for (const change of changes) {
        const { path, content, action = 'update' } = change;
        
        if (action === 'delete') {
          delete newFiles[path];
        } else if (action === 'create' || action === 'update') {
          const language = getLanguageFromPath(path);
          newFiles[path] = {
            name: path.split('/').pop(),
            language,
            content
          };
        }
      }
      
      return newFiles;
    });
  }, [setFiles]);

  return {
    updateFile,
    deleteFile,
    renameFile,
    createFile,
    getFile,
    getFileContent,
    fileExists,
    applyAICodeChanges
  };
}

function getLanguageFromPath(path) {
  const ext = path.split('.').pop()?.toLowerCase();
  const languageMap = {
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'css': 'css',
    'scss': 'scss',
    'html': 'html',
    'json': 'json',
    'md': 'markdown',
    'svg': 'xml',
    'xml': 'xml'
  };
  return languageMap[ext] || 'plaintext';
}

export default useVirtualFileSystem;
