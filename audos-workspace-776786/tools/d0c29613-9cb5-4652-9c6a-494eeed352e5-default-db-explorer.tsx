import { useState, useEffect, useCallback } from 'react';
import { PageHeader, Grid, Stack, StatCard, DataTable, Badge, Card, Tabs, Button, EmptyState } from 'dashboard-blocks';
import { Database, Table, Columns, GitBranch, Play, Download, Upload, RefreshCw, HardDrive, BarChart3, Trash2, Clock, Shield, Plus, Search, FileJson, FileSpreadsheet, Save, AlertCircle, CheckCircle, Eye, Edit, X, Copy } from 'lucide-react';

interface TemplateProps {
  workspaceId: string;
  authToken?: string;
}

interface TableInfo {
  tableName: string;
  columns: ColumnInfo[];
  indexes: any[];
  foreignKeys: any[];
  rowCount: number;
  sizeBytes: number;
  description?: string;
}

interface ColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
  primaryKey: boolean;
  unique: boolean;
  defaultValue: any;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export function DatabaseExplorer({ workspaceId, authToken }: TemplateProps) {
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('tables');
  const [selectedTable, setSelectedTable] = useState('');
  const [browserData, setBrowserData] = useState<any[]>([]);
  const [browserTotal, setBrowserTotal] = useState(0);
  const [browserPage, setBrowserPage] = useState(0);
  const [browserLoading, setBrowserLoading] = useState(false);
  const [browserSort, setBrowserSort] = useState('');
  const [browserOrder, setBrowserOrder] = useState<'asc' | 'desc'>('asc');
  const [editingRow, setEditingRow] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, any>>({});
  const [addingRow, setAddingRow] = useState(false);
  const [newRowValues, setNewRowValues] = useState<Record<string, any>>({});
  const [schemaTable, setSchemaTable] = useState('');
  const [schemaDetails, setSchemaDetails] = useState<TableInfo | null>(null);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [sqlQuery, setSqlQuery] = useState('SELECT * FROM ');
  const [queryResults, setQueryResults] = useState<any>(null);
  const [queryError, setQueryError] = useState('');
  const [queryLoading, setQueryLoading] = useState(false);
  const [exportTable, setExportTable] = useState('');
  const [exportFormat, setExportFormat] = useState('csv');
  const [importTable, setImportTable] = useState('');
  const [importData, setImportData] = useState('');
  const [importPreview, setImportPreview] = useState(0);
  const [importLoading, setImportLoading] = useState(false);
  const [backups, setBackups] = useState<any[]>([]);
  const [backupsLoading, setBackupsLoading] = useState(false);
  const [backupCreating, setBackupCreating] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{ type: string; id: string } | null>(null);
  const [usage, setUsage] = useState<any>(null);
  const [usageLoading, setUsageLoading] = useState(false);
  const [error, setError] = useState('');

  const baseUrl = `/api/workspaces/${workspaceId}/db`;
  const dataUrl = `/api/workspaces/${workspaceId}/data`;
  const __dt = typeof localStorage !== 'undefined' ? localStorage.getItem('workspace_device_token') : null;
  const authHeaders: Record<string, string> = authToken ? { 'Authorization': 'Bearer ' + authToken } : __dt ? { 'x-device-token': __dt } : {};

  const fetchTables = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const headers: Record<string, string> = authToken ? { 'Authorization': 'Bearer ' + authToken } : __dt ? { 'x-device-token': __dt } : {};
      const res = await fetch(`${baseUrl}/tables`, { credentials: 'include', headers });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        console.error('[DB Explorer] Failed to load tables (HTTP ' + res.status + '):', errData.error || 'Unknown error');
        setError('Failed to load tables (HTTP ' + res.status + '). ' + (errData.error || ''));
        setTables([]);
        return;
      }
      const data = await res.json();
      setTables(data.tables || []);
    } catch (err) {
      setError('Failed to load tables');
    } finally {
      setLoading(false);
    }
  }, [baseUrl, authToken]);

  useEffect(() => {
    fetchTables();
  }, [fetchTables]);

  const [browserAuthWarning, setBrowserAuthWarning] = useState('');

  const fetchBrowserData = useCallback(async (table: string, page = 0, sort = '', order = 'asc') => {
    if (!table) return;
    setBrowserLoading(true);
    setBrowserAuthWarning('');
    try {
      let url = `${dataUrl}/${table}?_limit=25&_offset=${page * 25}&_shared=1`;
      if (sort) url += `&_sort=${sort}&_order=${order}`;
      const res = await fetch(url, { credentials: 'include', headers: authHeaders });
      if (res.status === 401 || res.status === 403) {
        console.warn('[DB Explorer] Auth failed (' + res.status + '): device token may be expired or invalid. Re-authenticate from workspace settings.');
        setBrowserData([]);
        setBrowserTotal(0);
        setBrowserAuthWarning('Authentication failed (HTTP ' + res.status + '). Your device token may be expired. Please re-authenticate from workspace settings.');
        return;
      }
      const data = await res.json();
      const rows = data.data || [];
      const total = data.total || 0;
      if (rows.length === 0 && total === 0 && !__dt) {
        console.warn('[DB Explorer] Empty results without device token — data may be session-scoped. Authenticate for full access.');
        setBrowserAuthWarning('No data returned. You may not be authenticated — open workspace settings to sign in for full data access.');
      }
      setBrowserData(rows);
      setBrowserTotal(total);
    } catch (err) {
      console.error('Failed to fetch data:', err);
      setBrowserAuthWarning('Failed to fetch data. Check the console for details.');
    } finally {
      setBrowserLoading(false);
    }
  }, [dataUrl]);

  const handleSelectTableForBrowse = (tableName: string) => {
    setSelectedTable(tableName);
    setActiveTab('browser');
    setBrowserPage(0);
    fetchBrowserData(tableName, 0);
  };

  const handleSaveRow = async (id: string) => {
    try {
      await fetch(`${dataUrl}/${selectedTable}/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify(editValues),
        credentials: 'include',
      });
      setEditingRow(null);
      setEditValues({});
      fetchBrowserData(selectedTable, browserPage, browserSort, browserOrder);
    } catch (err) {
      console.error('Failed to update row:', err);
    }
  };

  const handleDeleteRow = async (id: string) => {
    if (!confirm('Delete this row?')) return;
    try {
      await fetch(`${dataUrl}/${selectedTable}/${id}`, { method: 'DELETE', credentials: 'include', headers: authHeaders });
      fetchBrowserData(selectedTable, browserPage, browserSort, browserOrder);
    } catch (err) {
      console.error('Failed to delete row:', err);
    }
  };

  const handleAddRow = async () => {
    try {
      await fetch(`${dataUrl}/${selectedTable}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify(newRowValues),
        credentials: 'include',
      });
      setAddingRow(false);
      setNewRowValues({});
      fetchBrowserData(selectedTable, browserPage, browserSort, browserOrder);
    } catch (err) {
      console.error('Failed to add row:', err);
    }
  };

  const fetchSchemaDetails = async (table: string) => {
    setSchemaLoading(true);
    try {
      const res = await fetch(`${baseUrl}/tables/${table}`, { credentials: 'include', headers: authHeaders });
      if (!res.ok) {
        console.error('[DB Explorer] Failed to fetch schema (HTTP ' + res.status + ')');
        setSchemaDetails(null);
        return;
      }
      const data = await res.json();
      setSchemaDetails(data);
    } catch (err) {
      console.error('Failed to fetch schema:', err);
    } finally {
      setSchemaLoading(false);
    }
  };

  const handleRunQuery = async () => {
    setQueryLoading(true);
    setQueryError('');
    setQueryResults(null);
    try {
      const res = await fetch(`${baseUrl}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ sql: sqlQuery }),
        credentials: 'include',
      });
      const data = await res.json();
      if (!res.ok) {
        setQueryError(data.error || data.message || 'Query failed');
      } else {
        setQueryResults(data);
      }
    } catch (err: any) {
      setQueryError(err.message || 'Query failed');
    } finally {
      setQueryLoading(false);
    }
  };

  const handleExport = async (table: string, format: string) => {
    try {
      const res = await fetch(`${baseUrl}/export/${table}?format=${format}`);
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${table}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('Export failed:', err.message);
    }
  };

  const handleImport = async () => {
    if (!importTable || !importData) return;
    setImportLoading(true);
    try {
      let parsed: any[];
      try {
        parsed = JSON.parse(importData);
        if (!Array.isArray(parsed)) parsed = [parsed];
      } catch {
        const lines = importData.trim().split('\n');
        const headers = lines[0].split(',').map(h => h.trim());
        parsed = lines.slice(1).map(line => {
          const vals = line.split(',').map(v => v.trim());
          const obj: Record<string, string> = {};
          headers.forEach((h, i) => { obj[h] = vals[i] || ''; });
          return obj;
        });
      }
      await fetch(`${baseUrl}/import/${importTable}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ data: parsed }),
        credentials: 'include',
      });
      setImportData('');
      setImportPreview(0);
      fetchTables();
    } catch (err) {
      console.error('Import failed:', err);
    } finally {
      setImportLoading(false);
    }
  };

  const fetchBackups = async () => {
    setBackupsLoading(true);
    try {
      const res = await fetch(`${baseUrl}/backups`, { credentials: 'include', headers: authHeaders });
      const data = await res.json();
      setBackups(data.backups || []);
    } catch (err) {
      console.error('Failed to fetch backups:', err);
    } finally {
      setBackupsLoading(false);
    }
  };

  const handleCreateBackup = async () => {
    setBackupCreating(true);
    try {
      await fetch(`${baseUrl}/backups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ description: 'Manual backup' }),
        credentials: 'include',
      });
      fetchBackups();
    } catch (err) {
      console.error('Failed to create backup:', err);
    } finally {
      setBackupCreating(false);
    }
  };

  const handleRestoreBackup = async (backupId: string) => {
    try {
      await fetch(`${baseUrl}/backups/${backupId}/restore`, { method: 'POST', credentials: 'include', headers: authHeaders });
      setConfirmAction(null);
      fetchTables();
    } catch (err) {
      console.error('Failed to restore backup:', err);
    }
  };

  const handleDeleteBackup = async (backupId: string) => {
    try {
      await fetch(`${baseUrl}/backups/${backupId}`, { method: 'DELETE', credentials: 'include', headers: authHeaders });
      setConfirmAction(null);
      fetchBackups();
    } catch (err) {
      console.error('Failed to delete backup:', err);
    }
  };

  const fetchUsage = async () => {
    setUsageLoading(true);
    try {
      const res = await fetch(`${baseUrl}/usage`, { credentials: 'include', headers: authHeaders });
      const data = await res.json();
      setUsage(data);
    } catch (err) {
      console.error('Failed to fetch usage:', err);
    } finally {
      setUsageLoading(false);
    }
  };

  const generateERDiagram = (): string => {
    if (tables.length === 0) return 'No tables found.';
    let diagram = 'erDiagram\n';
    tables.forEach(t => {
      t.columns.forEach(c => {
        diagram += `    ${t.tableName} {\n        ${c.type} ${c.name}${c.primaryKey ? ' PK' : ''}${c.unique ? ' UK' : ''}\n    }\n`;
      });
      (t.foreignKeys || []).forEach((fk: any) => {
        diagram += `    ${t.tableName} }o--|| ${fk.referencedTable} : "${fk.columnName}"\n`;
      });
    });
    return diagram;
  };

  useEffect(() => {
    if (importData) {
      try {
        const parsed = JSON.parse(importData);
        setImportPreview(Array.isArray(parsed) ? parsed.length : 1);
      } catch {
        const lines = importData.trim().split('\n');
        setImportPreview(Math.max(0, lines.length - 1));
      }
    } else {
      setImportPreview(0);
    }
  }, [importData]);

  const currentTableInfo = tables.find(t => t.tableName === selectedTable);
  const currentColumns = currentTableInfo?.columns || [];

  const tablesTab = (
    <Stack gap={4}>
      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading tables...</div>
      ) : tables.length === 0 ? (
        <EmptyState icon={<Database className="w-12 h-12" />} title="No Tables" description="Your database has no tables yet." />
      ) : (
        <Grid cols={3} gap={4}>
          {tables.map(t => (
            <Card key={t.tableName} title={t.tableName} actions={
              <Button size="sm" variant="secondary" onClick={() => handleSelectTableForBrowse(t.tableName)}>
                <Eye className="w-3 h-3" /> Browse
              </Button>
            }>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-500">Rows</span><span className="font-medium">{t.rowCount.toLocaleString()}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">Size</span><span className="font-medium">{formatBytes(t.sizeBytes)}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">Columns</span><span className="font-medium">{t.columns.length}</span></div>
                {t.description && <p className="text-gray-400 text-xs mt-1">{t.description}</p>}
              </div>
            </Card>
          ))}
        </Grid>
      )}
    </Stack>
  );

  const browserTab = (
    <Stack gap={4}>
      <div className="flex items-center gap-3 flex-wrap">
        <select
          className="border rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-800 dark:border-gray-600"
          value={selectedTable}
          onChange={(e) => {
            setSelectedTable(e.target.value);
            setBrowserPage(0);
            fetchBrowserData(e.target.value, 0);
          }}
        >
          <option value="">Select a table...</option>
          {tables.map(t => <option key={t.tableName} value={t.tableName}>{t.tableName}</option>)}
        </select>
        {selectedTable && (
          <>
            <Button size="sm" variant="primary" onClick={() => setAddingRow(true)}>
              <Plus className="w-3 h-3" /> Add Row
            </Button>
            <Button size="sm" variant="secondary" onClick={() => fetchBrowserData(selectedTable, browserPage, browserSort, browserOrder)}>
              <RefreshCw className="w-3 h-3" /> Refresh
            </Button>
            <span className="text-sm text-gray-500">{browserTotal} total rows</span>
          </>
        )}
      </div>

      {addingRow && selectedTable && (
        <Card title="Add New Row" actions={
          <div className="flex gap-2">
            <Button size="sm" variant="primary" onClick={handleAddRow}><Save className="w-3 h-3" /> Save</Button>
            <Button size="sm" variant="secondary" onClick={() => { setAddingRow(false); setNewRowValues({}); }}><X className="w-3 h-3" /> Cancel</Button>
          </div>
        }>
          <div className="grid grid-cols-3 gap-2">
            {currentColumns.filter(c => !c.primaryKey || !c.defaultValue).map(col => (
              <div key={col.name}>
                <label className="text-xs text-gray-500 block mb-1">{col.name} <span className="text-gray-400">({col.type})</span></label>
                <input
                  className="border rounded px-2 py-1 text-sm w-full dark:bg-gray-800 dark:border-gray-600"
                  placeholder={col.nullable ? 'NULL' : 'Required'}
                  value={newRowValues[col.name] || ''}
                  onChange={(e) => setNewRowValues(prev => ({ ...prev, [col.name]: e.target.value }))}
                />
              </div>
            ))}
          </div>
        </Card>
      )}

      {selectedTable && !browserLoading && browserData.length > 0 && (
        <>
          <div className="overflow-x-auto border rounded dark:border-gray-700">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  {currentColumns.map(col => (
                    <th
                      key={col.name}
                      className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700"
                      onClick={() => {
                        const newOrder = browserSort === col.name && browserOrder === 'asc' ? 'desc' : 'asc';
                        setBrowserSort(col.name);
                        setBrowserOrder(newOrder);
                        fetchBrowserData(selectedTable, browserPage, col.name, newOrder);
                      }}
                    >
                      {col.name} {browserSort === col.name ? (browserOrder === 'asc' ? '↑' : '↓') : ''}
                    </th>
                  ))}
                  <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Actions</th>
                </tr>
              </thead>
              <tbody>
                {browserData.map((row, idx) => {
                  const rowId = row.id || row._id || idx;
                  const isEditing = editingRow === String(rowId);
                  return (
                    <tr key={rowId} className="border-t dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      {currentColumns.map(col => (
                        <td key={col.name} className="px-3 py-1.5">
                          {isEditing ? (
                            <input
                              className="border rounded px-1.5 py-0.5 text-sm w-full dark:bg-gray-800 dark:border-gray-600"
                              value={editValues[col.name] ?? row[col.name] ?? ''}
                              onChange={(e) => setEditValues(prev => ({ ...prev, [col.name]: e.target.value }))}
                            />
                          ) : (
                            <span
                              className="cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-900/20 px-1 rounded"
                              onClick={() => { setEditingRow(String(rowId)); setEditValues({ ...row }); }}
                            >
                              {row[col.name] === null ? <span className="text-gray-400 italic">NULL</span> : String(row[col.name]).length > 200 ? String(row[col.name]).slice(0, 200) + '...' : String(row[col.name])}
                            </span>
                          )}
                        </td>
                      ))}
                      <td className="px-3 py-1.5">
                        <div className="flex gap-1">
                          {isEditing ? (
                            <>
                              <Button size="sm" variant="primary" onClick={() => handleSaveRow(String(rowId))}><Save className="w-3 h-3" /></Button>
                              <Button size="sm" variant="secondary" onClick={() => { setEditingRow(null); setEditValues({}); }}><X className="w-3 h-3" /></Button>
                            </>
                          ) : (
                            <>
                              <Button size="sm" variant="secondary" onClick={() => { setEditingRow(String(rowId)); setEditValues({ ...row }); }}><Edit className="w-3 h-3" /></Button>
                              <Button size="sm" variant="secondary" onClick={() => handleDeleteRow(String(rowId))}><Trash2 className="w-3 h-3" /></Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500">Page {browserPage + 1} of {Math.ceil(browserTotal / 25)}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={browserPage === 0} onClick={() => { setBrowserPage(p => p - 1); fetchBrowserData(selectedTable, browserPage - 1, browserSort, browserOrder); }}>Previous</Button>
              <Button size="sm" variant="secondary" disabled={(browserPage + 1) * 25 >= browserTotal} onClick={() => { setBrowserPage(p => p + 1); fetchBrowserData(selectedTable, browserPage + 1, browserSort, browserOrder); }}>Next</Button>
            </div>
          </div>
        </>
      )}

      {selectedTable && !browserLoading && browserData.length === 0 && (
        browserAuthWarning ? (
          <EmptyState icon={<AlertCircle className="w-12 h-12 text-amber-500" />} title="Data Unavailable" description={browserAuthWarning} />
        ) : (
          <EmptyState icon={<Table className="w-12 h-12" />} title="No Data" description="This table has no rows yet." action={<Button variant="primary" onClick={() => setAddingRow(true)}><Plus className="w-4 h-4" /> Add Row</Button>} />
        )
      )}
      {browserLoading && <div className="text-center py-8 text-gray-500">Loading data...</div>}
      {!selectedTable && <EmptyState icon={<Table className="w-12 h-12" />} title="Select a Table" description="Choose a table from the dropdown to browse its data." />}
    </Stack>
  );

  const schemaTab = (
    <Stack gap={4}>
      <div className="flex items-center gap-3">
        <select
          className="border rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-800 dark:border-gray-600"
          value={schemaTable}
          onChange={(e) => { setSchemaTable(e.target.value); if (e.target.value) fetchSchemaDetails(e.target.value); }}
        >
          <option value="">Select a table...</option>
          {tables.map(t => <option key={t.tableName} value={t.tableName}>{t.tableName}</option>)}
        </select>
      </div>

      {schemaLoading && <div className="text-center py-8 text-gray-500">Loading schema...</div>}

      {schemaDetails && !schemaLoading && (
        <Stack gap={4}>
          <Card title="Columns">
            <DataTable
              data={schemaDetails.columns}
              columns={[
                { key: 'name', header: 'Name', render: (val: string, row: any) => (
                  <span className="font-medium">{row.primaryKey ? '🔑 ' : ''}{val}</span>
                )},
                { key: 'type', header: 'Type', render: (val: string) => <Badge variant="info">{val}</Badge> },
                { key: 'nullable', header: 'Nullable', render: (val: boolean) => val ? <Badge variant="warning">YES</Badge> : <Badge variant="default">NO</Badge> },
                { key: 'unique', header: 'Unique', render: (val: boolean) => val ? <Badge variant="success">YES</Badge> : <span className="text-gray-400">-</span> },
                { key: 'defaultValue', header: 'Default', render: (val: any) => val !== null && val !== undefined ? <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 rounded">{String(val)}</code> : <span className="text-gray-400">-</span> },
              ]}
              pageSize={50}
              emptyMessage="No columns"
            />
          </Card>

          {schemaDetails.indexes && schemaDetails.indexes.length > 0 && (
            <Card title="Indexes">
              <DataTable
                data={schemaDetails.indexes}
                columns={[
                  { key: 'name', header: 'Index Name' },
                  { key: 'columns', header: 'Columns', render: (val: any) => Array.isArray(val) ? val.join(', ') : String(val) },
                  { key: 'unique', header: 'Unique', render: (val: boolean) => val ? <Badge variant="success">YES</Badge> : <Badge variant="default">NO</Badge> },
                ]}
                pageSize={20}
                emptyMessage="No indexes"
              />
            </Card>
          )}

          {schemaDetails.foreignKeys && schemaDetails.foreignKeys.length > 0 && (
            <Card title="Foreign Keys">
              <DataTable
                data={schemaDetails.foreignKeys}
                columns={[
                  { key: 'columnName', header: 'Column' },
                  { key: 'referencedTable', header: 'References Table' },
                  { key: 'referencedColumn', header: 'References Column' },
                ]}
                pageSize={20}
                emptyMessage="No foreign keys"
              />
            </Card>
          )}
        </Stack>
      )}

      {!schemaTable && <EmptyState icon={<Columns className="w-12 h-12" />} title="Select a Table" description="Choose a table to inspect its schema." />}
    </Stack>
  );

  const relationshipsTab = (
    <Stack gap={4}>
      <Card title="Entity Relationship Diagram" actions={
        <Button size="sm" variant="secondary" onClick={() => { navigator.clipboard.writeText(generateERDiagram()); }}>
          <Copy className="w-3 h-3" /> Copy
        </Button>
      }>
        {tables.length === 0 ? (
          <EmptyState icon={<GitBranch className="w-12 h-12" />} title="No Tables" description="Add tables to see relationships." />
        ) : (
          <pre className="bg-gray-50 dark:bg-gray-900 p-4 rounded text-sm overflow-x-auto font-mono whitespace-pre-wrap border dark:border-gray-700">{generateERDiagram()}</pre>
        )}
      </Card>
      {tables.length > 0 && (
        <Card title="Foreign Key Summary">
          <DataTable
            data={tables.flatMap(t => (t.foreignKeys || []).map((fk: any) => ({ sourceTable: t.tableName, column: fk.columnName, referencedTable: fk.referencedTable, referencedColumn: fk.referencedColumn })))}
            columns={[
              { key: 'sourceTable', header: 'Source Table', render: (val: string) => <Badge variant="info">{val}</Badge> },
              { key: 'column', header: 'Column' },
              { key: 'referencedTable', header: 'Target Table', render: (val: string) => <Badge variant="success">{val}</Badge> },
              { key: 'referencedColumn', header: 'Target Column' },
            ]}
            pageSize={20}
            emptyMessage="No foreign key relationships found."
          />
        </Card>
      )}
    </Stack>
  );

  const queryTab = (
    <Stack gap={4}>
      <Card title="SQL Query (SELECT only)">
        <div className="space-y-3">
          <textarea
            className="w-full border rounded p-3 font-mono text-sm h-32 dark:bg-gray-800 dark:border-gray-600 dark:text-white"
            value={sqlQuery}
            onChange={(e) => setSqlQuery(e.target.value)}
            placeholder="SELECT * FROM table_name LIMIT 100"
          />
          <div className="flex items-center gap-3">
            <Button variant="primary" onClick={handleRunQuery} disabled={queryLoading || !sqlQuery.trim()}>
              <Play className="w-4 h-4" /> {queryLoading ? 'Running...' : 'Run Query'}
            </Button>
            {queryResults && <span className="text-sm text-gray-500">{queryResults.rowCount} rows returned</span>}
          </div>
        </div>
      </Card>

      {queryError && (
        <Card>
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Error:</span>
            <span>{queryError}</span>
          </div>
        </Card>
      )}

      {queryResults && queryResults.rows && (
        <DataTable
          title="Query Results"
          data={queryResults.rows}
          columns={(queryResults.columns || Object.keys(queryResults.rows[0] || {})).map((col: string) => ({
            key: col,
            header: col,
            sortable: true,
            render: (val: any) => val === null ? <span className="text-gray-400 italic">NULL</span> : String(val).length > 500 ? String(val).slice(0, 500) + '...' : String(val),
          }))}
          pageSize={25}
          searchable
          emptyMessage="No results"
        />
      )}
    </Stack>
  );

  const importExportTab = (
    <Stack gap={4}>
      <Grid cols={2} gap={4}>
        <Card title="Export Data" actions={<Download className="w-4 h-4 text-gray-400" />}>
          <div className="space-y-3">
            <div>
              <label className="text-sm text-gray-500 block mb-1">Table</label>
              <select className="border rounded px-3 py-1.5 text-sm w-full bg-white dark:bg-gray-800 dark:border-gray-600" value={exportTable} onChange={(e) => setExportTable(e.target.value)}>
                <option value="">Select table...</option>
                {tables.map(t => <option key={t.tableName} value={t.tableName}>{t.tableName}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm text-gray-500 block mb-1">Format</label>
              <div className="flex gap-2">
                <button className={`px-3 py-1.5 rounded text-sm border ${exportFormat === 'csv' ? 'bg-blue-50 border-blue-300 text-blue-700 dark:bg-blue-900/30 dark:border-blue-600 dark:text-blue-400' : 'dark:border-gray-600'}`} onClick={() => setExportFormat('csv')}>
                  <FileSpreadsheet className="w-3 h-3 inline mr-1" /> CSV
                </button>
                <button className={`px-3 py-1.5 rounded text-sm border ${exportFormat === 'json' ? 'bg-blue-50 border-blue-300 text-blue-700 dark:bg-blue-900/30 dark:border-blue-600 dark:text-blue-400' : 'dark:border-gray-600'}`} onClick={() => setExportFormat('json')}>
                  <FileJson className="w-3 h-3 inline mr-1" /> JSON
                </button>
              </div>
            </div>
            <Button variant="primary" disabled={!exportTable} onClick={() => handleExport(exportTable, exportFormat)}>
              <Download className="w-4 h-4" /> Download {exportFormat.toUpperCase()}
            </Button>
          </div>
        </Card>

        <Card title="Import Data" actions={<Upload className="w-4 h-4 text-gray-400" />}>
          <div className="space-y-3">
            <div>
              <label className="text-sm text-gray-500 block mb-1">Table</label>
              <select className="border rounded px-3 py-1.5 text-sm w-full bg-white dark:bg-gray-800 dark:border-gray-600" value={importTable} onChange={(e) => setImportTable(e.target.value)}>
                <option value="">Select table...</option>
                {tables.map(t => <option key={t.tableName} value={t.tableName}>{t.tableName}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm text-gray-500 block mb-1">Data (JSON array or CSV)</label>
              <textarea
                className="w-full border rounded p-2 font-mono text-xs h-24 dark:bg-gray-800 dark:border-gray-600"
                value={importData}
                onChange={(e) => setImportData(e.target.value)}
                placeholder='[{"col1": "val1"}] or CSV with headers'
              />
            </div>
            {importPreview > 0 && <p className="text-sm text-gray-500"><CheckCircle className="w-3 h-3 inline text-green-500" /> {importPreview} row(s) detected</p>}
            <Button variant="primary" disabled={!importTable || !importData || importLoading} onClick={handleImport}>
              <Upload className="w-4 h-4" /> {importLoading ? 'Importing...' : 'Import Data'}
            </Button>
          </div>
        </Card>
      </Grid>
    </Stack>
  );

  const backupsTab = (
    <Stack gap={4}>
      <div className="flex items-center gap-3">
        <Button variant="primary" onClick={handleCreateBackup} disabled={backupCreating}>
          <Plus className="w-4 h-4" /> {backupCreating ? 'Creating...' : 'Create Backup'}
        </Button>
        <Button variant="secondary" onClick={fetchBackups}>
          <RefreshCw className="w-4 h-4" /> Refresh
        </Button>
      </div>

      {confirmAction && (
        <Card>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-amber-500" />
              <span className="font-medium">Confirm {confirmAction.type}?</span>
              <span className="text-sm text-gray-500">This action {confirmAction.type === 'restore' ? 'will overwrite current data' : 'cannot be undone'}.</span>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="primary" onClick={() => confirmAction.type === 'restore' ? handleRestoreBackup(confirmAction.id) : handleDeleteBackup(confirmAction.id)}>
                Confirm
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setConfirmAction(null)}>Cancel</Button>
            </div>
          </div>
        </Card>
      )}

      <DataTable
        title="Backups"
        data={backups}
        columns={[
          { key: 'description', header: 'Description', render: (val: string) => val || 'Unnamed backup' },
          { key: 'createdAt', header: 'Date', sortable: true, render: (val: string) => val ? new Date(val).toLocaleString() : '-' },
          { key: 'tableCount', header: 'Tables', render: (val: number) => val ?? '-' },
          { key: 'totalRows', header: 'Rows', render: (val: number) => val?.toLocaleString() ?? '-' },
          { key: 'sizeBytes', header: 'Size', render: (val: number) => val ? formatBytes(val) : '-' },
          { key: 'id', header: 'Actions', render: (id: string) => (
            <div className="flex gap-1">
              <Button size="sm" variant="secondary" onClick={() => setConfirmAction({ type: 'restore', id })}><RefreshCw className="w-3 h-3" /> Restore</Button>
              <Button size="sm" variant="secondary" onClick={() => setConfirmAction({ type: 'delete', id })}><Trash2 className="w-3 h-3" /> Delete</Button>
            </div>
          )},
        ]}
        loading={backupsLoading}
        emptyMessage="No backups yet. Create one to protect your data."
      />
    </Stack>
  );

  const usageTab = (
    <Stack gap={4}>
      {!usage && !usageLoading && (
        <Button variant="secondary" onClick={fetchUsage}><BarChart3 className="w-4 h-4" /> Load Usage Data</Button>
      )}
      {usageLoading && <div className="text-center py-8 text-gray-500">Loading usage...</div>}
      {usage && (
        <>
          <Grid cols={3} gap={4}>
            <StatCard
              title="Tables"
              value={`${usage.summary?.tableCount ?? tables.length} / ${usage.quota?.maxTables ?? '∞'}`}
              subtitle={`${usage.quota?.maxTables ? Math.round(((usage.summary?.tableCount ?? tables.length) / usage.quota.maxTables) * 100) : 0}% used`}
              icon={<Table className="w-5 h-5" />}
            />
            <StatCard
              title="Total Rows"
              value={(usage.summary?.totalRows ?? 0).toLocaleString()}
              subtitle={`Max: ${usage.quota?.maxRowsPerTable?.toLocaleString() ?? '∞'} per table`}
              icon={<Database className="w-5 h-5" />}
            />
            <StatCard
              title="Storage"
              value={formatBytes(usage.summary?.totalSizeBytes ?? 0)}
              subtitle={`Max: ${usage.quota?.maxStorageBytes ? formatBytes(usage.quota.maxStorageBytes) : '∞'}`}
              icon={<HardDrive className="w-5 h-5" />}
            />
          </Grid>

          {usage.quota?.maxTables && (
            <Card title="Quota Usage">
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1"><span>Tables</span><span>{usage.summary?.tableCount ?? tables.length} / {usage.quota.maxTables}</span></div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2"><div className="bg-blue-500 rounded-full h-2" style={{ width: `${Math.min(100, ((usage.summary?.tableCount ?? tables.length) / usage.quota.maxTables) * 100)}%` }} /></div>
                </div>
                {usage.quota.maxStorageBytes && (
                  <div>
                    <div className="flex justify-between text-sm mb-1"><span>Storage</span><span>{formatBytes(usage.summary?.totalSizeBytes ?? 0)} / {formatBytes(usage.quota.maxStorageBytes)}</span></div>
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2"><div className="bg-green-500 rounded-full h-2" style={{ width: `${Math.min(100, ((usage.summary?.totalSizeBytes ?? 0) / usage.quota.maxStorageBytes) * 100)}%` }} /></div>
                  </div>
                )}
              </div>
            </Card>
          )}

          {usage.tables && usage.tables.length > 0 && (
            <DataTable
              title="Per-Table Breakdown"
              data={usage.tables}
              columns={[
                { key: 'tableName', header: 'Table', sortable: true },
                { key: 'rowCount', header: 'Rows', sortable: true, render: (val: number) => val?.toLocaleString() ?? '0' },
                { key: 'sizeBytes', header: 'Size', sortable: true, render: (val: number) => formatBytes(val || 0) },
                { key: 'sizeBytes', header: 'Share', render: (val: number) => {
                  const total = usage.summary?.totalSizeBytes || 1;
                  const pct = Math.round((val / total) * 100);
                  return (
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5"><div className="bg-blue-500 rounded-full h-1.5" style={{ width: `${pct}%` }} /></div>
                      <span className="text-xs text-gray-500">{pct}%</span>
                    </div>
                  );
                }},
              ]}
              pageSize={20}
              emptyMessage="No table data"
            />
          )}
        </>
      )}
    </Stack>
  );

  return (
    <Stack>
      <PageHeader
        title="Database Explorer"
        subtitle={`${tables.length} tables in workspace`}
        icon={<Database className="w-5 h-5 text-blue-600" />}
        actions={
          <Button variant="secondary" onClick={fetchTables}>
            <RefreshCw className="w-4 h-4" /> Refresh
          </Button>
        }
      />

      <div className="rounded-md border border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/40 p-3 text-sm text-blue-900 dark:text-blue-100">
        <div className="flex items-start gap-2">
          <Plus className="w-4 h-4 mt-0.5 shrink-0" />
          <div className="space-y-1">
            <div className="font-medium">How to populate this database</div>
            <div className="text-blue-800/90 dark:text-blue-200/90 leading-relaxed">
              This shows your <span className="font-medium">private workspace schema</span> — separate from the platform event lake that powers the Analytics dashboard. To create tables, open the Agent panel and ask Otto, e.g.{' '}
              <span className="italic">"Create a <code className="font-mono text-xs">customers</code> table with name + email, and a <code className="font-mono text-xs">bookings</code> table that links to it with date, status, and price."</span>{' '}
              Otto will generate the DDL, run it against your schema, and the tables will appear here. Power users can also connect with a normal Postgres client using the credentials in the <span className="font-medium">Usage</span> tab, or call{' '}
              <code className="font-mono text-xs">POST /api/workspaces/:wsId/db/setup-schema</code> for a default starter schema.
            </div>
          </div>
        </div>
      </div>

      <Tabs
        defaultTab="tables"
        tabs={[
          { id: 'tables', label: 'Tables', content: tablesTab },
          { id: 'browser', label: 'Browser', content: browserTab },
          { id: 'schema', label: 'Schema', content: schemaTab },
          { id: 'relationships', label: 'Relationships', content: relationshipsTab },
          { id: 'query', label: 'Query', content: queryTab },
          { id: 'import-export', label: 'Import/Export', content: importExportTab },
          { id: 'backups', label: 'Backups', content: backupsTab },
          { id: 'usage', label: 'Usage', content: usageTab },
        ]}
      />
    </Stack>
  );
}
