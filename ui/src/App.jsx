import React, { useState, useEffect } from 'react';
import {
  FolderOpen,
  Hash,
  Archive,
  FileType,
  Loader2,
  Undo2,
  ListFilter,
  Layers,
  Copy,
  CalendarClock,
  BarChart3,
  HardDrive,
  FileSearch,
  FileType2,
  X,
  Plus,
  RefreshCw,
  Pencil,
  Save,
  Scissors,
} from 'lucide-react';

const App = () => {
  // — Core state —
  const [path, setPath] = useState('');
  const [prefix, setPrefix] = useState('Item_');
  const [oldExt, setOldExt] = useState('.zip');
  const [newExt, setNewExt] = useState('.cbr');
  const [sortMode, setSortMode] = useState('name');
  const [isDryRun, setIsDryRun] = useState(false);
  const [filterText, setFilterText] = useState('');
  const [status, setStatus] = useState({ type: '', message: '' });
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  const [hasHistory, setHasHistory] = useState(false);
  const [useRegex, setUseRegex] = useState(false);
  const [dateGrain, setDateGrain] = useState('month');
  const [duplicates, setDuplicates] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // — New feature state —
  const [customRules, setCustomRules] = useState([]);
  const [showRulesEditor, setShowRulesEditor] = useState(false);
  const [newRuleFolder, setNewRuleFolder] = useState('');
  const [newRuleExts, setNewRuleExts] = useState('');
  const [newRuleKeywords, setNewRuleKeywords] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // — Progress listener —
  useEffect(() => {
    const handleProgress = (e) => setProgress(e.detail);
    window.addEventListener('progressUpdate', handleProgress);
    return () => window.removeEventListener('progressUpdate', handleProgress);
  }, []);

  // — Auto-load stats + rules when path changes —
  useEffect(() => {
    if (path) {
      refreshStats();
      loadRules();
    }
  }, [path]);

  // ─────────────────────────────────────────────
  // Core helpers
  // ─────────────────────────────────────────────

  const refreshStats = async () => {
    if (!path || !window.pywebview?.api) return;
    const res = await window.pywebview.api.analyze_workspace(path);
    if (res.success) setStats(res.stats);
  };

  const loadRules = async () => {
    if (!path || !window.pywebview?.api) return;
    const res = await window.pywebview.api.load_rules(path);
    if (res.success) {
      if (res.rules?.length > 0) setCustomRules(res.rules);
      setHasHistory(res.has_history);
    }
  };

  const handleRefreshStats = async () => {
    setIsRefreshing(true);
    await refreshStats();
    setIsRefreshing(false);
    addLog('Workspace stats refreshed.', 'info');
  };

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [{ timestamp, message, type }, ...prev].slice(0, 50));
  };

  const showStatus = (type, message) => {
    setStatus({ type, message });
    addLog(message, type);
    setTimeout(() => setStatus({ type: '', message: '' }), 5000);
  };

  // ─────────────────────────────────────────────
  // Folder selection
  // ─────────────────────────────────────────────

  const handleSelectFolder = async () => {
    try {
      if (window.pywebview && window.pywebview.api) {
        const result = await window.pywebview.api.select_folder();
        if (result) {
          setPath(result);
          addLog(`Selected workspace: ${result}`, 'success');
        }
      } else {
        const mockPath = "";
        setPath(mockPath);
        showStatus('info', 'Dev Mode: Mock path selected');
      }
    } catch (err) {
      showStatus('error', 'Failed to select folder');
    }
  };

  // ─────────────────────────────────────────────
  // Generic operation runner
  // ─────────────────────────────────────────────

  // Operations that produce an undo-able history
  const UNDOABLE_OPS = ['sequential_rename', 'sort_by_date', 'flatten_workspace', 'smart_categorize'];

  const runOperation = async (opName, ...args) => {
    if (!path) {
      showStatus('error', 'Please select a path first');
      return;
    }

    let finalArgs = [...args];
    if (opName === 'sequential_rename') {
      finalArgs = [prefix, 'files', sortMode, isDryRun, filterText, useRegex];
    } else if (opName === 'change_extensions') {
      finalArgs = [oldExt, newExt, isDryRun, filterText];
    } else if (opName === 'delete_duplicates') {
      finalArgs = [duplicates, isDryRun];
    } else if (opName === 'sort_by_date') {
      finalArgs = [dateGrain, isDryRun];
    } else if (opName === 'smart_categorize') {
      finalArgs = [isDryRun, customRules];
    } else {
      finalArgs = [...args, isDryRun];
    }

    const opTitle = opName
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');

    addLog(`${isDryRun ? '[SIMULATION] ' : ''}Starting ${opTitle}...`, 'info');
    setLoading(true);
    setProgress(0);

    try {
      if (window.pywebview && window.pywebview.api) {
        const result = await window.pywebview.api[opName](path, ...finalArgs);

        if (result.success) {
          showStatus(isDryRun ? 'info' : 'success', result.message);
          if (UNDOABLE_OPS.includes(opName) && !isDryRun) setHasHistory(true);
          if (opName === 'undo_last_operation') setHasHistory(false);
          if (opName === 'find_duplicates') setDuplicates(result.duplicates || []);
          if (opName === 'delete_duplicates') setDuplicates([]);
          refreshStats();
        } else {
          showStatus('error', result.error);
        }
      } else {
        setTimeout(() => {
          showStatus('success', `Mock ${opName} completed!`);
          setLoading(false);
          refreshStats();
        }, 1000);
      }
    } catch (err) {
      showStatus('error', `Operation failed: ${err.message}`);
    } finally {
      if (window.pywebview && window.pywebview.api) setLoading(false);
      setProgress(0);
    }
  };

  const handleSelectFile = async (file) => {
    if (!window.pywebview?.api) return;
    const res = await window.pywebview.api.get_file_metadata(file.path);
    if (res.success) {
      setSelectedFile(res.metadata);
      setSidebarOpen(true);
    }
  };

  // ─────────────────────────────────────────────
  // Custom rules handlers
  // ─────────────────────────────────────────────

  const handleAddRule = () => {
    if (!newRuleFolder.trim()) return;
    const rule = {
      folder: newRuleFolder.trim(),
      extensions: newRuleExts
        .split(',')
        .map((e) => e.trim())
        .filter(Boolean),
      keywords: newRuleKeywords
        .split(',')
        .map((k) => k.trim())
        .filter(Boolean),
    };
    setCustomRules((prev) => [...prev, rule]);
    setNewRuleFolder('');
    setNewRuleExts('');
    setNewRuleKeywords('');
  };

  const handleDeleteRule = (idx) =>
    setCustomRules((prev) => prev.filter((_, i) => i !== idx));

  const handleSaveRules = async () => {
    if (!path || !window.pywebview?.api) {
      showStatus('error', 'Not connected to backend');
      return;
    }
    const res = await window.pywebview.api.save_rules(path, customRules);
    showStatus(res.success ? 'success' : 'error', res.success ? res.message : res.error);
  };

  // ─────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────

  return (
    <div className="min-h-screen p-8 text-slate-100 flex flex-row gap-8 max-h-screen overflow-hidden bg-[#0f172a]">

      {/* ── Main Content ── */}
      <div className={`flex-1 flex flex-col transition-all duration-300 ${sidebarOpen ? 'mr-0' : ''}`}>

        {/* Header */}
        <header className="w-full flex justify-between items-center shrink-0 mb-6">
          <div className="flex items-center gap-4">
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent leading-tight">
                Organizer Pro <span className="text-xs align-top text-slate-500 font-normal ml-1">V4</span>
              </h1>
              <p className="text-slate-400 font-medium">Personal Asset Intelligence</p>
            </div>
            {hasHistory && (
              <button
                onClick={() => runOperation('undo_last_operation')}
                className="ml-4 flex items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl hover:bg-red-500/20 transition-all"
              >
                <Undo2 className="w-4 h-4" />
                <span className="text-[10px] font-bold uppercase tracking-widest leading-none">Undo</span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-4">
            {/* Workspace stats pill */}
            {stats && (
              <div className="hidden lg:flex items-center gap-4 px-5 py-2 bg-slate-900/40 rounded-2xl border border-slate-700/30 backdrop-blur-sm">
                <div className="flex flex-col">
                  <span className="text-[9px] uppercase tracking-widest text-slate-500 mb-0.5">Total Size</span>
                  <div className="flex items-baseline gap-1">
                    <span className="text-lg font-bold text-slate-200">{stats.total_size_str.split(' ')[0]}</span>
                    <span className="text-[10px] text-slate-500">{stats.total_size_str.split(' ')[1]}</span>
                  </div>
                </div>
                <div className="h-8 w-px bg-slate-800" />
                <div className="flex gap-2">
                  {Object.entries(stats.categories).slice(0, 3).map(([cat, size]) => (
                    <div key={cat} className="flex flex-col items-center">
                      <div className="text-[9px] text-slate-500 mb-1">{cat}</div>
                      <div className="w-12 h-1 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${cat === 'Media' ? 'bg-accent' : cat === 'Documents' ? 'bg-emerald-400' : 'bg-primary'}`}
                          style={{ width: `${Math.min(100, (size / stats.total_size) * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <button
                  onClick={handleRefreshStats}
                  disabled={isRefreshing}
                  title="Refresh stats"
                  className="p-1.5 text-slate-600 hover:text-slate-300 transition-colors disabled:opacity-40"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
                </button>
              </div>
            )}

            {/* Simulation toggle */}
            <div className="flex items-center gap-3 bg-slate-900/50 px-4 py-2 rounded-xl border border-slate-700/50">
              <span className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Simulation</span>
              <button
                onClick={() => setIsDryRun(!isDryRun)}
                className={`w-10 h-5 rounded-full p-1 transition-colors relative ${isDryRun ? 'bg-accent' : 'bg-slate-700'}`}
              >
                <div className={`w-3 h-3 bg-white rounded-full transition-transform ${isDryRun ? 'translate-x-5' : 'translate-x-0'}`} />
              </button>
            </div>
          </div>
        </header>

        {/* 3-column grid */}
        <main className="w-full flex-1 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 overflow-y-auto pr-2 pb-8 custom-scrollbar">

          {/* ── Workspace Path (full-width) ── */}
          <section className="md:col-span-2 lg:col-span-3 glass-card flex flex-col gap-4 border-primary/20 bg-primary/5">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <FolderOpen className="w-5 h-5 text-primary" /> Active Workspace
              </h2>
              <div className="flex items-center gap-2 bg-slate-950/60 rounded-lg px-3 py-1.5 border border-white/5">
                <ListFilter className="w-3.5 h-3.5 text-slate-500" />
                <input
                  type="text"
                  placeholder="Live Filter..."
                  value={filterText}
                  onChange={(e) => setFilterText(e.target.value)}
                  className="bg-transparent border-none outline-none text-[10px] text-slate-300 w-32"
                />
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex-1 bg-black/30 border border-white/5 rounded-xl px-4 py-3 text-slate-400 font-mono text-[11px] overflow-hidden truncate">
                {path || 'Select a folder to begin...'}
              </div>
              <button
                onClick={handleSelectFolder}
                className="btn-primary flex items-center gap-2 whitespace-nowrap"
                disabled={loading}
              >
                <HardDrive className="w-4 h-4" /> Browse
              </button>
              {path && (
                <button
                  onClick={handleRefreshStats}
                  disabled={isRefreshing}
                  title="Refresh workspace analysis"
                  className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 border border-white/5 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-700/50 transition-all disabled:opacity-40"
                >
                  <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                </button>
              )}
            </div>
          </section>

          {/* ── Column 1: Rename & Tools ── */}
          <div className="flex flex-col gap-6">

            {/* Renamer */}
            <div className="glass-card flex flex-col gap-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold flex items-center gap-3">
                  <Hash className="w-6 h-6 text-accent" /> Renamer
                </h3>
                <div className="flex bg-slate-900 rounded-lg p-1 border border-white/5">
                  <button
                    onClick={() => setSortMode('name')}
                    className={`px-2 py-0.5 text-[8px] uppercase rounded ${sortMode === 'name' ? 'bg-primary text-white' : 'text-slate-600'}`}
                  >Name</button>
                  <button
                    onClick={() => setSortMode('date')}
                    className={`px-2 py-0.5 text-[8px] uppercase rounded ${sortMode === 'date' ? 'bg-primary text-white' : 'text-slate-600'}`}
                  >Date</button>
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <div className="text-[9px] uppercase font-bold text-slate-600">Pattern</div>
                  <button
                    onClick={() => setUseRegex(!useRegex)}
                    className={`text-[8px] px-1.5 py-0.5 rounded border transition-colors ${useRegex ? 'bg-indigo-500/20 border-indigo-500/50 text-indigo-400' : 'bg-slate-800 border-white/5 text-slate-600'}`}
                  >REGEX</button>
                </div>
                <input
                  type="text"
                  value={prefix}
                  onChange={(e) => setPrefix(e.target.value)}
                  className="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-2 text-xs"
                  placeholder="Prefix or Replacement..."
                />
                <div className="flex gap-2">
                  <button onClick={() => runOperation('sequential_rename')} className="btn-primary flex-1 py-1.5 text-xs">Files</button>
                  <button onClick={() => runOperation('sequential_rename', prefix, 'folders')} className="btn-ghost flex-1 py-1.5 text-xs">Folders</button>
                </div>
              </div>
            </div>

            {/* Extension Changer — new card */}
            <div className="glass-card flex flex-col gap-4 border-cyan-500/20">
              <h3 className="text-lg font-bold flex items-center gap-3">
                <Scissors className="w-6 h-6 text-cyan-400" /> Ext Changer
              </h3>
              <div className="space-y-3">
                <div className="flex gap-2 items-end">
                  <div className="flex-1">
                    <div className="text-[9px] uppercase font-bold text-slate-600 mb-1">From</div>
                    <input
                      type="text"
                      value={oldExt}
                      onChange={(e) => setOldExt(e.target.value)}
                      className="w-full bg-black/30 border border-white/10 rounded-xl px-3 py-2 text-xs font-mono text-cyan-400 text-center"
                      placeholder=".zip"
                    />
                  </div>
                  <span className="text-slate-600 pb-2 shrink-0">→</span>
                  <div className="flex-1">
                    <div className="text-[9px] uppercase font-bold text-slate-600 mb-1">To</div>
                    <input
                      type="text"
                      value={newExt}
                      onChange={(e) => setNewExt(e.target.value)}
                      className="w-full bg-black/30 border border-white/10 rounded-xl px-3 py-2 text-xs font-mono text-cyan-400 text-center"
                      placeholder=".cbr"
                    />
                  </div>
                </div>
                <button
                  onClick={() => runOperation('change_extensions')}
                  className="btn-primary w-full text-xs py-2.5 !bg-cyan-700 hover:!bg-cyan-600"
                >
                  Apply Extension Change
                </button>
              </div>
            </div>

            {/* Maintenance */}
            <div className="glass-card flex flex-col gap-4">
              <h3 className="text-[10px] font-bold text-slate-600 uppercase tracking-widest">Maintenance</h3>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => runOperation('zip_folders')}
                  className="flex flex-col items-center gap-2 p-3 bg-white/5 rounded-xl border border-white/5 hover:bg-white/10 transition-all"
                >
                  <Archive className="w-5 h-5 text-emerald-400" />
                  <span className="text-[9px] uppercase">Zip Subdirs</span>
                </button>
                <button
                  onClick={() => runOperation('flatten_workspace')}
                  className="flex flex-col items-center gap-2 p-3 bg-white/5 rounded-xl border border-white/5 hover:bg-white/10 transition-all"
                >
                  <Layers className="w-5 h-5 text-indigo-400" />
                  <span className="text-[9px] uppercase">Flatten</span>
                </button>
              </div>
            </div>
          </div>

          {/* ── Column 2: Intelligence & Sorting ── */}
          <div className="flex flex-col gap-6">

            {/* Rule Engine — with custom rules editor */}
            <div className="glass-card flex flex-col gap-4 border-indigo-500/20">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold flex items-center gap-3">
                  <BarChart3 className="w-6 h-6 text-indigo-400" /> Rule Engine
                </h3>
                <button
                  onClick={() => setShowRulesEditor(!showRulesEditor)}
                  className={`text-[8px] px-2 py-1 border rounded-lg flex items-center gap-1 transition-colors ${
                    showRulesEditor
                      ? 'bg-indigo-500/20 border-indigo-500/30 text-indigo-400'
                      : 'bg-slate-800 border-white/5 text-slate-500 hover:text-slate-300'
                  }`}
                >
                  <Pencil className="w-2.5 h-2.5" />
                  {showRulesEditor ? 'Done' : 'Edit Rules'}
                </button>
              </div>

              {showRulesEditor ? (
                <div className="space-y-3">
                  {/* Current rules list */}
                  <div className="space-y-2 max-h-36 overflow-y-auto custom-scrollbar">
                    {customRules.length === 0 ? (
                      <div className="text-[10px] text-slate-600 italic text-center py-3">
                        No custom rules. Using built-in defaults.
                      </div>
                    ) : (
                      customRules.map((rule, idx) => (
                        <div key={idx} className="flex items-start gap-2 p-2 bg-white/5 rounded-lg border border-white/5">
                          <div className="flex-1 min-w-0">
                            <div className="text-[10px] font-bold text-indigo-300 truncate">→ {rule.folder}</div>
                            {rule.extensions?.length > 0 && (
                              <div className="text-[8px] text-slate-500 font-mono">{rule.extensions.join('  ')}</div>
                            )}
                            {rule.keywords?.length > 0 && (
                              <div className="text-[8px] text-slate-600">kw: {rule.keywords.join(', ')}</div>
                            )}
                          </div>
                          <button
                            onClick={() => handleDeleteRule(idx)}
                            className="text-red-400/40 hover:text-red-400 shrink-0 transition-colors mt-0.5"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Add new rule form */}
                  <div className="space-y-1.5 pt-2 border-t border-white/5">
                    <input
                      type="text"
                      placeholder="Folder name (e.g. Design)"
                      value={newRuleFolder}
                      onChange={(e) => setNewRuleFolder(e.target.value)}
                      className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-1.5 text-[10px]"
                    />
                    <input
                      type="text"
                      placeholder="Extensions, comma-separated (.psd, .ai)"
                      value={newRuleExts}
                      onChange={(e) => setNewRuleExts(e.target.value)}
                      className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-1.5 text-[10px]"
                    />
                    <input
                      type="text"
                      placeholder="Keywords, comma-separated (logo, brand)"
                      value={newRuleKeywords}
                      onChange={(e) => setNewRuleKeywords(e.target.value)}
                      className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-1.5 text-[10px]"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={handleAddRule}
                        className="flex-1 py-1.5 bg-indigo-500/20 border border-indigo-500/30 text-indigo-400 rounded-lg text-[9px] font-bold uppercase flex items-center justify-center gap-1 hover:bg-indigo-500/30 transition-all"
                      >
                        <Plus className="w-3 h-3" /> Add
                      </button>
                      <button
                        onClick={handleSaveRules}
                        className="flex-1 py-1.5 bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 rounded-lg text-[9px] font-bold uppercase flex items-center justify-center gap-1 hover:bg-emerald-500/30 transition-all"
                      >
                        <Save className="w-3 h-3" /> Save to Disk
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <p className="text-xs text-slate-400">
                    Sort files into smart folders using{' '}
                    {customRules.length > 0 ? (
                      <span className="text-indigo-400 font-bold">{customRules.length} custom rule{customRules.length > 1 ? 's' : ''}</span>
                    ) : (
                      'built-in defaults'
                    )}.
                  </p>
                  <button
                    onClick={() => runOperation('smart_categorize')}
                    className="btn-primary !bg-indigo-600 hover:!bg-indigo-500 text-xs py-2.5"
                  >
                    Apply Smart Rules
                  </button>
                </>
              )}
            </div>

            {/* Time Capsule */}
            <div className="glass-card flex flex-col gap-5 border-emerald-500/20">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold flex items-center gap-3">
                  <CalendarClock className="w-6 h-6 text-emerald-400" /> Time Capsule
                </h3>
                <div className="flex bg-slate-900 rounded-lg p-0.5 border border-white/5">
                  {['month', 'day'].map((g) => (
                    <button
                      key={g}
                      onClick={() => setDateGrain(g)}
                      className={`px-2 py-0.5 text-[8px] uppercase rounded ${dateGrain === g ? 'bg-emerald-600 text-white' : 'text-slate-600'}`}
                    >{g}</button>
                  ))}
                </div>
              </div>
              <button
                onClick={() => runOperation('sort_by_date')}
                className="btn-primary !bg-emerald-600 hover:!bg-emerald-500 text-xs py-2.5"
              >
                Date Sort
              </button>
            </div>

            {/* Duplicates */}
            <div className="glass-card flex flex-col gap-4 border-red-500/20">
              <h3 className="text-lg font-bold flex items-center gap-3">
                <Copy className="w-6 h-6 text-red-400" /> Duplicates
              </h3>
              {duplicates.length > 0 ? (
                <div className="p-3 bg-red-500/5 border border-red-500/10 rounded-xl text-center">
                  <div className="text-[10px] text-red-300 font-bold mb-2">{duplicates.length} GROUPS FOUND</div>
                  <button
                    onClick={() => runOperation('delete_duplicates')}
                    className="w-full py-2 bg-red-600 hover:bg-red-500 text-[10px] font-bold rounded-lg uppercase transition-all"
                  >
                    Wipe Duplicates
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => runOperation('find_duplicates')}
                  className="btn-primary !bg-red-600 hover:!bg-red-500 text-xs py-2.5"
                >
                  Scan Workspace
                </button>
              )}
            </div>
          </div>

          {/* ── Column 3: Asset Analysis ── */}
          <div className="flex flex-col gap-6">
            <div className="glass-card flex flex-col h-full overflow-hidden border-amber-500/20">
              <h3 className="text-lg font-bold flex items-center gap-3 mb-4">
                <FileSearch className="w-6 h-6 text-amber-400" /> Largest Assets
              </h3>
              <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar min-h-[300px]">
                {stats?.top_files.map((file, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleSelectFile(file)}
                    className="p-2.5 bg-white/5 border border-white/5 rounded-xl hover:bg-white/10 transition-all cursor-pointer group"
                  >
                    <div className="flex justify-between items-start gap-2">
                      <span className="text-[11px] font-medium truncate text-slate-300 group-hover:text-primary flex-1">{file.name}</span>
                      <span className="text-[10px] font-mono text-amber-400 shrink-0">{file.size_str}</span>
                    </div>
                    <div className="mt-1 text-[8px] text-slate-600 uppercase tracking-widest">{file.type}</div>
                  </div>
                ))}
                {!stats && (
                  <div className="text-center py-12 text-slate-700 text-xs italic">
                    Select a folder to analyze...
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── Activity Log (full-width) ── */}
          <div className="md:col-span-2 lg:col-span-3 glass-card !bg-black/40 border-white/5 max-h-[160px]">
            <div className="flex justify-between items-center mb-3">
              <span className="text-[9px] font-bold uppercase tracking-widest text-slate-600">Engine Output</span>
              <button onClick={() => setLogs([])} className="text-slate-800 hover:text-slate-500 text-[9px]">Flush</button>
            </div>
            <div className="overflow-y-auto text-[10px] font-mono flex flex-col gap-1 pr-2 custom-scrollbar">
              {logs.map((log, i) => (
                <div key={i} className="flex gap-2">
                  <span className="text-slate-700 shrink-0">[{log.timestamp}]</span>
                  <span
                    className={
                      log.type === 'error'
                        ? 'text-red-500'
                        : log.type === 'success'
                        ? 'text-emerald-400'
                        : 'text-slate-400'
                    }
                  >
                    {log.message}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </main>
      </div>

      {/* ── Preview Sidebar ── */}
      {sidebarOpen && selectedFile && (
        <div className="w-80 bg-[#0f172a] border-l border-white/5 h-screen overflow-y-auto p-6 fixed right-0 top-0 z-50 shadow-2xl animate-in slide-in-from-right">
          <div className="flex justify-between items-center mb-8">
            <h3 className="text-sm font-bold uppercase tracking-widest text-primary">Asset Preview</h3>
            <button onClick={() => setSidebarOpen(false)} className="text-slate-500 hover:text-white">
              <X className="w-6 h-6" />
            </button>
          </div>

          <div className="aspect-square bg-black/40 rounded-2xl border border-white/10 flex items-center justify-center mb-6 overflow-hidden">
            {['.jpg', '.jpeg', '.png', '.gif', '.webp'].includes(selectedFile.extension) ? (
              <img src={selectedFile.uri} className="w-full h-full object-contain p-2" alt={selectedFile.name} />
            ) : ['.mp4', '.webm', '.mov'].includes(selectedFile.extension) ? (
              <video src={selectedFile.uri} controls className="w-full h-full" />
            ) : (
              <FileType2 className="w-16 h-16 text-slate-800 opacity-20" />
            )}
          </div>

          <div className="space-y-6">
            <div>
              <div className="text-[9px] uppercase font-bold text-slate-600 mb-1">Filename</div>
              <div className="text-xs text-slate-200 break-all">{selectedFile.name}</div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-[9px] uppercase font-bold text-slate-600 mb-1">Size</div>
                <div className="text-xs text-amber-400 font-mono">{selectedFile.size}</div>
              </div>
              <div>
                <div className="text-[9px] uppercase font-bold text-slate-600 mb-1">Type</div>
                <div className="text-xs text-primary uppercase">{selectedFile.extension}</div>
              </div>
            </div>
            <div>
              <div className="text-[9px] uppercase font-bold text-slate-600 mb-1">Modified</div>
              <div className="text-xs text-slate-400">{selectedFile.modified}</div>
            </div>
            <button
              onClick={() => {
                setPrefix(selectedFile.name.split('.')[0]);
                setSidebarOpen(false);
              }}
              className="w-full py-3 bg-primary/10 border border-primary/30 text-primary rounded-xl text-[10px] font-bold uppercase tracking-widest hover:bg-primary/20 transition-all"
            >
              Renamer Shortcut
            </button>
          </div>
        </div>
      )}

      {/* ── Loading Overlay ── */}
      {loading && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex flex-col items-center justify-center z-[100]">
          <div className="relative">
            <Loader2 className="w-20 h-20 text-primary animate-spin opacity-20" />
            <div className="absolute inset-0 flex items-center justify-center text-primary font-bold">{progress}%</div>
          </div>
          <p className="mt-4 text-[10px] font-bold text-primary tracking-[0.3em] uppercase">Engine Processing</p>
        </div>
      )}
    </div>
  );
};

export default App;
