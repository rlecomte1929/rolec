import { useState, useEffect } from 'react';
import { File, Folder, Eye, Edit } from 'lucide-react';
import { useSpaceRuntime } from '../SpaceRuntimeContext';

interface FileAccessLog {
  timestamp: number;
  path: string;
  action: 'read' | 'write';
  tool: string;
}

interface FileBrowserProps {
  fileAccessLogs?: FileAccessLog[];
}

export default function FileBrowser({ fileAccessLogs = [] }: FileBrowserProps) {
  const { readFile, writeFile, listFiles, spaceId, sessionId } = useSpaceRuntime();
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [files, setFiles] = useState<any[]>([]);
  const [initialized, setInitialized] = useState(false);

  // Initialize session with template data on first visit
  useEffect(() => {
    const initializeSession = async () => {
      if (initialized) return;
      
      try {
        // Check if session already has data files
        const sessionFiles = await listFiles('data');
        const hasData = sessionFiles.some(f => 
          !f.path.endsWith('.gitkeep') && 
          (f.path.endsWith('.json') || f.path.endsWith('.txt'))
        );
        
        if (!hasData) {
          console.log('[FileBrowser] Initializing session with template data...');
          
          // Copy template data files from space to session
          const templateResponse = await fetch(`/api/space/${spaceId}/files?path=data`);
          if (templateResponse.ok) {
            const templateData = await templateResponse.json();
            const templateFiles = templateData.files || [];
            
            for (const file of templateFiles) {
              if (file.path.endsWith('.gitkeep')) continue;
              
              // Read template file
              const contentResponse = await fetch(`/api/space/${spaceId}/file/${file.path}`);
              if (contentResponse.ok) {
                const { content } = await contentResponse.json();
                // Write to session
                await writeFile(file.path, content);
                console.log(`[FileBrowser] Initialized ${file.path}`);
              }
            }
          }
        }
        
        setInitialized(true);
      } catch (error) {
        console.error('[FileBrowser] Failed to initialize session:', error);
        setInitialized(true); // Don't block on errors
      }
    };
    
    initializeSession();
  }, [spaceId, sessionId, listFiles, writeFile, initialized]);

  // Load file list from SESSION directory (user-specific)
  useEffect(() => {
    if (!initialized) return;
    
    const loadFiles = async () => {
      try {
        const allFiles = await listFiles('data');
        
        // Filter to only show data files (JSON, TXT, CSV, MD) - exclude .gitkeep
        const filteredFiles = allFiles.filter((file: any) => {
          if (file.isDirectory) return false;
          const path = file.path.toLowerCase();
          if (path.endsWith('.gitkeep')) return false;
          return (
            path.endsWith('.json') || 
            path.endsWith('.txt') || 
            path.endsWith('.csv') || 
            path.endsWith('.md')
          );
        });
        
        setFiles(filteredFiles);
        console.log(`[FileBrowser] Loaded ${filteredFiles.length} session data files`);
      } catch (error) {
        console.error('[FileBrowser] Failed to load files:', error);
      }
    };
    
    loadFiles();
  }, [listFiles, initialized]);

  const loadFileContent = async (path: string, showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      const content = await readFile(path);
      setFileContent(content || '');
      setSelectedFile(path);
    } catch (error) {
      console.error('Failed to load file:', error);
      setFileContent('Error loading file');
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  // Auto-refresh selected file every 2 seconds
  useEffect(() => {
    if (!selectedFile) return;
    
    const interval = setInterval(() => {
      loadFileContent(selectedFile, false);
    }, 2000);
    
    return () => clearInterval(interval);
  }, [selectedFile]);

  const getRecentAccess = (path: string) => {
    const logs = fileAccessLogs.filter(log => log.path.includes(path));
    if (logs.length === 0) return null;
    return logs[logs.length - 1];
  };

  // Group files by directory
  const filesByDir: Record<string, string[]> = {};
  files.forEach(file => {
    const parts = file.path.split('/');
    const dir = parts.length > 1 ? parts.slice(0, -1).join('/') : 'root';
    if (!filesByDir[dir]) filesByDir[dir] = [];
    filesByDir[dir].push(file.path);
  });

  return (
    <div className="h-full flex bg-white">
      {/* File Tree */}
      <div className="w-1/3 border-r overflow-auto p-3">
        {Object.keys(filesByDir).length === 0 ? (
          <p className="text-xs text-gray-500 mt-4">No data files yet</p>
        ) : (
          Object.entries(filesByDir).map(([dir, filePaths]) => (
            <div key={dir} className="mb-4">
              <div className="flex items-center gap-2 mb-1 text-sm font-medium text-gray-600">
                <Folder className="w-4 h-4" />
                {dir}/
              </div>
              <div className="ml-6 space-y-1">
                {filePaths.map(path => {
                  const fileName = path.split('/').pop() || path;
                  const recentAccess = getRecentAccess(path);
                  return (
                    <button
                      key={path}
                      onClick={() => loadFileContent(path)}
                      className={`w-full text-left flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-100 transition-colors ${
                        selectedFile === path ? 'bg-blue-100 text-blue-700' : 'text-gray-700'
                      }`}
                    >
                      <File className="w-3 h-3" />
                      <span className="text-xs flex-1">{fileName}</span>
                      {recentAccess && (
                        <span className={`text-xs px-1 rounded ${
                          recentAccess.action === 'read' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
                        }`}>
                          {recentAccess.action === 'read' ? <Eye className="w-3 h-3" /> : <Edit className="w-3 h-3" />}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>

      {/* File Content */}
      <div className="flex-1 flex flex-col">
        <div className="p-3 border-b bg-gray-50">
          <h3 className="text-sm font-medium text-gray-700">
            {selectedFile || 'Select a file to view'}
          </h3>
        </div>
        <div className="flex-1 overflow-auto p-3">
          {loading ? (
            <p className="text-sm text-gray-500">Loading...</p>
          ) : selectedFile ? (
            <pre className="text-xs font-mono whitespace-pre-wrap bg-gray-50 p-3 rounded">
              {fileContent}
            </pre>
          ) : (
            <div className="text-center text-gray-500 mt-8">
              <File className="w-12 h-12 mx-auto mb-3 text-gray-400" />
              <p className="text-sm">Select a file from the left to view its contents</p>
            </div>
          )}
        </div>

        {/* File Access Log */}
        {fileAccessLogs.length > 0 && (
          <div className="border-t p-3 bg-gray-50 max-h-48 overflow-auto">
            <h3 className="text-xs font-semibold mb-2 text-gray-700">Recent Activity</h3>
            <div className="space-y-1">
              {[...fileAccessLogs].reverse().slice(0, 10).map((log, idx) => (
                <div key={idx} className="text-xs flex items-center gap-2 text-gray-600">
                  {log.action === 'read' ? (
                    <Eye className="w-3 h-3 text-blue-600" />
                  ) : (
                    <Edit className="w-3 h-3 text-green-600" />
                  )}
                  <span className="flex-1">{log.path}</span>
                  <span className="text-gray-400">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
