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
  ShieldAlert,
  Trash2,
  Wand2,
  PackageOpen,
  FolderSync,
  ImageIcon,
  MoveRight,
  Music,
  FileUp,
  Settings,
  ChevronRight,
  Gauge,
  FileJson,
  RotateCcw,
  FileText,
  ExternalLink,
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
  const [activeView, setActiveView] = useState('dashboard');
  const [imgQuality, setImgQuality] = useState(85);
  const [audioFiles, setAudioFiles] = useState([]);
  const [pdfFiles, setPdfFiles] = useState([]);
  const [imageFiles, setImageFiles] = useState([]);
  const [mediaError, setMediaError] = useState("");
  const [removeOriginalMp3, setRemoveOriginalMp3] = useState(false);
  const [removeOriginalPdf, setRemoveOriginalPdf] = useState(false);
  const [removeOriginalImage, setRemoveOriginalImage] = useState(false);

  // — Rule Engine state —
  const [customRules, setCustomRules] = useState([]);
  const [showRulesEditor, setShowRulesEditor] = useState(false);
  const [newRuleFolder, setNewRuleFolder] = useState('');
  const [newRuleExts, setNewRuleExts] = useState('');
  const [newRuleKeywords, setNewRuleKeywords] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // — System warning state —
  const [showSystemWarning, setShowSystemWarning] = useState(false);
  const [pendingSystemPath, setPendingSystemPath] = useState('');

  // — Advanced Automation state —
  const [automationDays, setAutomationDays] = useState(90);
  const [automationThresholdMb, setAutomationThresholdMb] = useState(500);
  const [regexPattern, setRegexPattern] = useState('');
  const [regexReplacement, setRegexReplacement] = useState('');
  const [backupDest, setBackupDest] = useState('');
  const [imgSourceExts, setImgSourceExts] = useState('.png,.bmp');
  const [imgTargetExt, setImgTargetExt] = useState('.webp');

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
      refreshMediaFiles();
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

  const refreshMediaFiles = async () => {
    if (!path) {
      setMediaError("No workspace selected.");
      return;
    }
    if (!window.pywebview?.api) {
      setMediaError("Backend API not found. If running in browser, pywebview is unavailable.");
      return;
    }
    try {
      if (typeof window.pywebview.api.get_audio_files !== 'function' ||
          typeof window.pywebview.api.get_pdf_files !== 'function' ||
          typeof window.pywebview.api.get_image_files !== 'function') {
        setMediaError("New API methods not found. Please restart the application.");
        return;
      }
      setMediaError("Loading...");
      const resAudio = await window.pywebview.api.get_audio_files(path);
      const resPdf = await window.pywebview.api.get_pdf_files(path);
      const resImage = await window.pywebview.api.get_image_files(path);

      if (resAudio && resAudio.success) setAudioFiles(resAudio.files || []);
      if (resPdf && resPdf.success) setPdfFiles(resPdf.files || []);
      if (resImage && resImage.success) setImageFiles(resImage.files || []);
      
      setMediaError("");
    } catch (err) {
      console.error("Failed to fetch media files:", err);
      setMediaError(err.toString());
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
          if (result.system_warning) {
            setPendingSystemPath(result.path);
            setShowSystemWarning(true);
          } else {
            setPath(result.path);
            addLog(`Selected workspace: ${result.path}`, 'success');
          }
        }
      } else {
        setPath('C:\\Users\\Demo\\Documents');
        showStatus('info', 'Dev Mode: Mock path selected');
      }
    } catch (err) {
      showStatus('error', 'Failed to select folder');
    }
  };

  const handleConfirmSystemPath = () => {
    setPath(pendingSystemPath);
    addLog(`⚠️ System-critical workspace selected: ${pendingSystemPath}`, 'error');
    setShowSystemWarning(false);
    setPendingSystemPath('');
  };

  const handleSelectBackupDest = async () => {
    try {
      if (window.pywebview?.api) {
        const result = await window.pywebview.api.select_folder();
        if (result && !result.system_warning) setBackupDest(result.path);
        else if (result?.system_warning) showStatus('error', 'Cannot use system-critical folder as backup destination.');
      }
    } catch (err) { showStatus('error', 'Failed to select folder'); }
  };

  // ─────────────────────────────────────────────
  // Media Service Handlers
  // ─────────────────────────────────────────────

  const handleOpenInExplorer = (filePath) => {
    if (window.pywebview?.api?.open_in_explorer) {
      window.pywebview.api.open_in_explorer(filePath);
    }
  };

  const handleMP3toWAV = async (filePath) => {
    if (!window.pywebview?.api) return;
    
    setLoading(true);
    setProgress(0);
    const res = await window.pywebview.api.convert_mp3_to_wav(filePath, removeOriginalMp3);
    setLoading(false);
    setProgress(0);
    showStatus(res.success ? 'success' : 'error', res.success ? res.message : res.error);
    if (res.success) {
      refreshStats();
      refreshMediaFiles();
    }
  };

  const handleBatchMP3toWAV = async () => {
    if (!path || !window.pywebview?.api) return;
    setLoading(true);
    setProgress(0);
    const res = await window.pywebview.api.batch_convert_mp3_to_wav(path, removeOriginalMp3, isDryRun);
    setLoading(false);
    setProgress(0);
    showStatus(res.success ? 'success' : 'error', res.success ? res.message : res.error);
    refreshStats();
    refreshMediaFiles();
  };

  const handleCompressPDF = async (filePath) => {
    if (!window.pywebview?.api) return;
    setLoading(true);
    setProgress(0);
    const res = await window.pywebview.api.compress_pdf(filePath, removeOriginalPdf);
    setLoading(false);
    setProgress(0);
    showStatus(res.success ? 'success' : 'error', res.success ? res.message : res.error);
    if (res.success) {
      refreshStats();
      refreshMediaFiles();
    }
  };

  const handleBatchCompressPDF = async () => {
    if (!path || !window.pywebview?.api) return;
    setLoading(true);
    setProgress(0);
    const res = await window.pywebview.api.batch_compress_pdf(path, removeOriginalPdf, isDryRun);
    setLoading(false);
    setProgress(0);
    showStatus(res.success ? 'success' : 'error', res.success ? res.message : res.error);
    refreshStats();
    refreshMediaFiles();
  };

  const handleOptimizeImage = async (filePath) => {
    if (!window.pywebview?.api) return;
    setLoading(true);
    setProgress(0);
    const res = await window.pywebview.api.optimize_image(filePath, imgQuality, removeOriginalImage);
    setLoading(false);
    setProgress(0);
    showStatus(res.success ? 'success' : 'error', res.success ? res.message : res.error);
    if (res.success) {
      refreshStats();
      refreshMediaFiles();
    }
  };

  const handleBatchOptimizeImages = async () => {
    if (!path || !window.pywebview?.api) return;
    setLoading(true);
    setProgress(0);
    const res = await window.pywebview.api.optimize_images(path, imgQuality, removeOriginalImage, isDryRun);
    setLoading(false);
    setProgress(0);
    showStatus(res.success ? 'success' : 'error', res.success ? res.message : res.error);
    refreshStats();
    refreshMediaFiles();
  };

  // ─────────────────────────────────────────────
  // Generic operation runner
  // ─────────────────────────────────────────────

  // Operations that produce an undo-able history
  const UNDOABLE_OPS = [
    'sequential_rename', 'sort_by_date', 'flatten_workspace', 'smart_categorize',
    'advanced_regex_rename', 'cleanup_old_files', 'archive_large_files', 'convert_image_formats',
  ];

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

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Gauge, group: 'General' },
    { id: 'renamer', label: 'Renamer', icon: Hash, group: 'Organizer' },
    { id: 'extensions', label: 'Ext Changer', icon: Scissors, group: 'Organizer' },
    { id: 'smart', label: 'Smart Sort', icon: Wand2, group: 'Organizer' },
    { id: 'date', label: 'Date Sorter', icon: CalendarClock, group: 'Organizer' },
    { id: 'media', label: 'Media Tools', icon: Music, group: 'Processing' },
    { id: 'advanced', label: 'Advanced Tools', icon: Layers, group: 'Processing' },
    { id: 'rules', label: 'Custom Rules', icon: Pencil, group: 'System' },
    { id: 'stats', label: 'Analytics', icon: BarChart3, group: 'System' },
  ];

  const renderWorkspace = () => {
    switch (activeView) {
      case 'dashboard':
        return (
          <div className="grid grid-cols-2 gap-6 p-8 overflow-y-auto custom-scrollbar">
            <div className="col-span-2 glass-card border-primary/20 bg-primary/5">
              <h2 className="text-xl font-bold flex items-center gap-3 mb-4 text-primary">
                <FolderOpen className="w-6 h-6" /> Workspace Status
              </h2>
              <div className="flex gap-4 items-center">
                <div className="flex-1 bg-black/40 border border-slate-700/50 rounded-xl px-4 py-3 text-slate-400 font-mono text-xs truncate">
                  {path || 'Connect a directory to begin...'}
                </div>
                <button onClick={handleSelectFolder} className="btn-primary flex items-center gap-2 whitespace-nowrap">
                  <HardDrive className="w-4 h-4" /> Change Folder
                </button>
              </div>
            </div>

            {stats && (
              <>
                <div className="glass-card flex flex-col gap-2">
                  <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Total Size</span>
                  <div className="text-3xl font-bold text-slate-100">{stats.total_size_str}</div>
                  <div className="text-[10px] text-slate-400">Current active directory volume</div>
                </div>
                <div className="glass-card flex flex-col gap-2">
                  <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Categories</span>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {Object.entries(stats.categories).map(([cat, size]) => (
                      <div key={cat} className="px-2 py-1 bg-slate-800 rounded-lg text-[10px] border border-white/5">
                        <span className="text-slate-400">{cat}:</span> <span className="text-primary font-bold">{Math.round(size / 1024 / 1024)}MB</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            <div className="col-span-2 grid grid-cols-3 gap-6">
               <button onClick={() => setActiveView('renamer')} className="p-6 glass-card border-accent/20 hover:bg-accent/5 flex flex-col items-center gap-3 text-center">
                 <Hash className="w-8 h-8 text-accent" />
                 <span className="font-bold text-sm">Renamer</span>
               </button>
               <button onClick={() => setActiveView('media')} className="p-6 glass-card border-music/20 hover:bg-music/5 flex flex-col items-center gap-3 text-center">
                 <Music className="w-8 h-8 text-pink-400" />
                 <span className="font-bold text-sm">Media Tools</span>
               </button>
               <button onClick={() => setActiveView('smart')} className="p-6 glass-card border-indigo-500/20 hover:bg-indigo-500/5 flex flex-col items-center gap-3 text-center">
                 <Wand2 className="w-8 h-8 text-indigo-400" />
                 <span className="font-bold text-sm">Smart Sort</span>
               </button>
            </div>
          </div>
        );

      case 'smart':
        return (
          <div className="p-8 max-w-2xl mx-auto space-y-8">
            <div className="glass-card border-indigo-500/20 bg-indigo-500/5">
              <h2 className="text-2xl font-bold flex items-center gap-3 mb-6">
                <Wand2 className="w-8 h-8 text-indigo-400" /> Smart Categorizer
              </h2>
              <div className="space-y-6">
                <p className="text-sm text-slate-400 leading-relaxed">
                  Automatically sort files into folders based on their extensions and keywords using the rules defined in the 
                  <button onClick={() => setActiveView('rules')} className="text-indigo-400 font-bold hover:underline mx-1">Rules Editor</button>.
                </p>
                
                <div className="p-4 bg-black/40 border border-slate-700/50 rounded-xl space-y-3">
                   <div className="text-[10px] font-black uppercase tracking-widest text-slate-500">Active Rules: {customRules.length}</div>
                   <div className="flex flex-wrap gap-2">
                      {customRules.slice(0, 5).map((r, i) => (
                        <span key={i} className="px-2 py-1 bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-[10px] rounded-lg">/{r.folder}</span>
                      ))}
                      {customRules.length > 5 && <span className="text-[10px] text-slate-600">+{customRules.length - 5} more</span>}
                   </div>
                </div>

                <button onClick={() => runOperation('smart_categorize')} className="w-full btn-primary !bg-indigo-600 hover:!bg-indigo-500 py-4 text-lg font-bold">
                  Run Smart Sorting Engine
                </button>
              </div>
            </div>
          </div>
        );

      case 'date':
        return (
          <div className="p-8 max-w-2xl mx-auto space-y-8">
            <div className="glass-card border-orange-500/20 bg-orange-500/5">
              <h2 className="text-2xl font-bold flex items-center gap-3 mb-6">
                <CalendarClock className="w-8 h-8 text-orange-400" /> Date-Based Organizer
              </h2>
              <div className="space-y-8">
                <p className="text-sm text-slate-400 leading-relaxed">
                  Organize your files into a chronological folder structure based on their last modification date.
                </p>

                <div className="space-y-4">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block px-1">Grouping Granularity</label>
                  <div className="grid grid-cols-3 gap-3">
                    {['year', 'month', 'day'].map(grain => (
                      <button 
                        key={grain}
                        onClick={() => setDateGrain(grain)}
                        className={`py-3 rounded-xl border text-xs font-bold uppercase transition-all ${dateGrain === grain ? 'bg-orange-500/20 border-orange-500/50 text-orange-400 shadow-lg shadow-orange-500/10' : 'bg-slate-900 border-white/5 text-slate-500 hover:bg-slate-800'}`}
                      >
                        {grain}
                      </button>
                    ))}
                  </div>
                </div>

                <button onClick={() => runOperation('sort_by_date')} className="w-full btn-primary !bg-orange-600 hover:!bg-orange-500 py-4 text-lg font-bold">
                  Organize by Date
                </button>
              </div>
            </div>
          </div>
        );

      case 'renamer':
        return (
          <div className="p-8 max-w-2xl mx-auto space-y-8 overflow-y-auto">
            <div className="glass-card">
              <h2 className="text-2xl font-bold flex items-center gap-3 mb-6">
                <Hash className="w-8 h-8 text-accent" /> Sequential Renamer
              </h2>
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-400">Sorting Priority</span>
                  <div className="flex bg-slate-900 rounded-xl p-1 border border-white/5">
                    <button onClick={() => setSortMode('name')} className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all ${sortMode === 'name' ? 'bg-primary shadow-lg' : 'text-slate-600'}`}>NAME</button>
                    <button onClick={() => setSortMode('date')} className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all ${sortMode === 'date' ? 'bg-primary shadow-lg' : 'text-slate-600'}`}>DATE</button>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <div className="flex justify-between items-center px-1">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Naming Pattern</label>
                    <button onClick={() => setUseRegex(!useRegex)} className={`px-2 py-0.5 text-[9px] font-bold rounded border ${useRegex ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-400' : 'bg-slate-800 border-white/5 text-slate-600'}`}>REGEX MODE</button>
                  </div>
                  <input type="text" value={prefix} onChange={(e) => setPrefix(e.target.value)} className="glass-input w-full" placeholder="Enter prefix (e.g. Photo_)" />
                </div>

                <div className="flex gap-4">
                   <button onClick={() => runOperation('sequential_rename')} className="btn-primary flex-1 py-4">Rename Files</button>
                   <button onClick={() => runOperation('sequential_rename', prefix, 'folders')} className="btn-ghost flex-1 py-4">Rename Folders</button>
                </div>
              </div>
            </div>

            <div className="glass-card border-slate-800">
               <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">Live Filter</h3>
               <div className="flex items-center gap-3 glass-input">
                  <ListFilter className="w-4 h-4 text-slate-500" />
                  <input type="text" value={filterText} onChange={(e) => setFilterText(e.target.value)} className="bg-transparent border-none outline-none text-sm w-full" placeholder="Limit operation to files matching..." />
               </div>
            </div>
          </div>
        );

      case 'extensions':
        return (
          <div className="p-8 max-w-2xl mx-auto space-y-8">
            <div className="glass-card border-cyan-500/20">
              <h2 className="text-2xl font-bold flex items-center gap-3 mb-6">
                <Scissors className="w-8 h-8 text-cyan-400" /> Extension Changer
              </h2>
              <div className="space-y-8">
                <div className="flex items-center gap-6">
                  <div className="flex-1 space-y-2">
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block px-1">Source Extension</label>
                    <input type="text" value={oldExt} onChange={(e) => setOldExt(e.target.value)} className="glass-input w-full py-4 text-lg font-mono text-cyan-400 text-center" placeholder=".jpg" />
                  </div>
                  <div className="pt-6"><MoveRight className="w-6 h-6 text-slate-700" /></div>
                  <div className="flex-1 space-y-2">
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block px-1">Target Extension</label>
                    <input type="text" value={newExt} onChange={(e) => setNewExt(e.target.value)} className="glass-input w-full py-4 text-lg font-mono text-primary text-center" placeholder=".webp" />
                  </div>
                </div>
                <button onClick={() => runOperation('change_extensions')} className="w-full btn-primary !bg-cyan-700 hover:!bg-cyan-600 py-4 text-lg font-bold">Apply Mass Extension Change</button>
              </div>
            </div>
          </div>
        );

      case 'media':
        return (
          <div className="p-8 grid grid-cols-2 gap-6 overflow-y-auto custom-scrollbar">
            <div className="col-span-2 mb-2">
              <h2 className="text-2xl font-bold flex items-center gap-3">
                <Music className="w-8 h-8 text-pink-400" /> Media Processing Hub
              </h2>
              <p className="text-slate-400 mt-1">Professional optimization tools for audio, documents, and imagery.</p>
            </div>

            <div className="col-span-2 glass-card border-pink-500/20 bg-pink-500/5 flex flex-col gap-4">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-pink-500/20 flex items-center justify-center shrink-0">
                    <Music className="w-5 h-5 text-pink-400" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white">MP3 to WAV Converter</h3>
                    <p className="text-xs text-slate-500">Convert audio files losslessly. {audioFiles.length} file(s) found.</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <button onClick={refreshMediaFiles} className="btn-ghost py-2 px-4 flex items-center justify-center gap-2 text-xs shrink-0 border border-slate-700">
                    <RotateCcw className="w-4 h-4" /> Refresh
                  </button>
                  <label className="flex items-center gap-2 text-xs text-pink-300 cursor-pointer">
                    <input 
                      type="checkbox" 
                      checked={removeOriginalMp3} 
                      onChange={(e) => setRemoveOriginalMp3(e.target.checked)}
                      className="accent-pink-500"
                    />
                    Remove original .mp3
                  </label>
                  <button onClick={handleBatchMP3toWAV} className="btn-primary !bg-pink-600 hover:!bg-pink-500 py-2 px-4 flex items-center justify-center gap-2 text-xs shrink-0">
                    <Settings className="w-4 h-4" /> Convert All
                  </button>
                </div>
              </div>

              {mediaError && (
                <div className="text-center py-4 bg-red-500/10 rounded-xl border border-red-500/20">
                  <p className="text-xs text-red-400 font-medium">{mediaError}</p>
                </div>
              )}

              {!mediaError && audioFiles.length > 0 ? (
                <div className="mt-2 max-h-[200px] overflow-y-auto custom-scrollbar pr-2 space-y-2">
                  {audioFiles.map((file, idx) => (
                    <div key={idx} className="flex justify-between items-center p-3 bg-black/40 rounded-xl border border-white/5 hover:border-pink-500/20 transition-all">
                      <div className="flex items-center gap-3 overflow-hidden">
                        <Music className="w-4 h-4 text-pink-400 shrink-0" />
                        <span className="text-xs truncate text-slate-300" title={file.name}>{file.name}</span>
                        <span className="text-[10px] text-slate-500 shrink-0 bg-black/40 px-2 py-0.5 rounded">{file.size}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => handleOpenInExplorer(file.path)} className="shrink-0 p-1.5 text-slate-500 hover:text-pink-400 transition-colors" title="Open in Explorer">
                          <ExternalLink className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => handleMP3toWAV(file.path)} className="shrink-0 px-3 py-1.5 bg-pink-500/10 text-pink-400 hover:bg-pink-500/20 rounded-lg text-xs font-bold transition-all border border-pink-500/20 hover:border-pink-500/40">
                          Convert
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : !mediaError ? (
                <div className="text-center py-8 text-xs text-slate-500 italic bg-black/20 rounded-xl border border-white/5">
                  No .mp3 files found in the current workspace.
                </div>
              ) : null}
            </div>

            <div className="col-span-2 glass-card border-red-500/20 bg-red-500/5 flex flex-col gap-4">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center shrink-0">
                    <FileJson className="w-5 h-5 text-red-400" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white">PDF Compressor</h3>
                    <p className="text-xs text-slate-500">Reduce PDF file size. {pdfFiles.length} file(s) found.</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <button onClick={refreshMediaFiles} className="btn-ghost py-2 px-4 flex items-center justify-center gap-2 text-xs shrink-0 border border-slate-700">
                    <RotateCcw className="w-4 h-4" /> Refresh
                  </button>
                  <label className="flex items-center gap-2 text-xs text-red-300 cursor-pointer">
                    <input 
                      type="checkbox" 
                      checked={removeOriginalPdf} 
                      onChange={(e) => setRemoveOriginalPdf(e.target.checked)}
                      className="accent-red-500"
                    />
                    Remove original .pdf
                  </label>
                  <button onClick={handleBatchCompressPDF} className="btn-primary !bg-red-700 hover:!bg-red-600 py-2 px-4 flex items-center justify-center gap-2 text-xs shrink-0">
                    <Settings className="w-4 h-4" /> Compress All
                  </button>
                </div>
              </div>

              {!mediaError && pdfFiles.length > 0 ? (
                <div className="mt-2 max-h-[200px] overflow-y-auto custom-scrollbar pr-2 space-y-2">
                  {pdfFiles.map((file, idx) => (
                    <div key={idx} className="flex justify-between items-center p-3 bg-black/40 rounded-xl border border-white/5 hover:border-red-500/20 transition-all">
                      <div className="flex items-center gap-3 overflow-hidden">
                        <FileJson className="w-4 h-4 text-red-400 shrink-0" />
                        <span className="text-xs truncate text-slate-300" title={file.name}>{file.name}</span>
                        <span className="text-[10px] text-slate-500 shrink-0 bg-black/40 px-2 py-0.5 rounded">{file.size}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => handleOpenInExplorer(file.path)} className="shrink-0 p-1.5 text-slate-500 hover:text-red-400 transition-colors" title="Open in Explorer">
                          <ExternalLink className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => handleCompressPDF(file.path)} className="shrink-0 px-3 py-1.5 bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded-lg text-xs font-bold transition-all border border-red-500/20 hover:border-red-500/40">
                          Compress
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : !mediaError ? (
                <div className="text-center py-8 text-xs text-slate-500 italic bg-black/20 rounded-xl border border-white/5">
                  No .pdf files found in the current workspace.
                </div>
              ) : null}
            </div>

            <div className="col-span-2 glass-card border-emerald-500/20 bg-emerald-500/5 flex flex-col gap-4">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center shrink-0">
                    <ImageIcon className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white">Image Optimizer</h3>
                    <p className="text-xs text-slate-500">Batch optimize images. {imageFiles.length} file(s) found.</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="flex flex-col items-end gap-1 mr-4">
                    <span className="text-[10px] font-bold text-slate-500 uppercase">Quality: {imgQuality}%</span>
                    <input type="range" min="10" max="100" value={imgQuality} onChange={(e) => setImgQuality(Number(e.target.value))} className="w-24 accent-emerald-500" />
                  </div>
                  <button onClick={refreshMediaFiles} className="btn-ghost py-2 px-4 flex items-center justify-center gap-2 text-xs shrink-0 border border-slate-700">
                    <RotateCcw className="w-4 h-4" /> Refresh
                  </button>
                  <label className="flex items-center gap-2 text-xs text-emerald-300 cursor-pointer">
                    <input 
                      type="checkbox" 
                      checked={removeOriginalImage} 
                      onChange={(e) => setRemoveOriginalImage(e.target.checked)}
                      className="accent-emerald-500"
                    />
                    Remove original
                  </label>
                  <button onClick={handleBatchOptimizeImages} className="btn-primary !bg-emerald-600 hover:!bg-emerald-500 py-2 px-4 flex items-center justify-center gap-2 text-xs shrink-0">
                    <Settings className="w-4 h-4" /> Optimize All
                  </button>
                </div>
              </div>

              {!mediaError && imageFiles.length > 0 ? (
                <div className="mt-2 max-h-[200px] overflow-y-auto custom-scrollbar pr-2 space-y-2">
                  {imageFiles.map((file, idx) => (
                    <div key={idx} className="flex justify-between items-center p-3 bg-black/40 rounded-xl border border-white/5 hover:border-emerald-500/20 transition-all">
                      <div className="flex items-center gap-3 overflow-hidden">
                        <ImageIcon className="w-4 h-4 text-emerald-400 shrink-0" />
                        <span className="text-xs truncate text-slate-300" title={file.name}>{file.name}</span>
                        <span className="text-[10px] text-slate-500 shrink-0 bg-black/40 px-2 py-0.5 rounded">{file.size}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => handleOpenInExplorer(file.path)} className="shrink-0 p-1.5 text-slate-500 hover:text-emerald-400 transition-colors" title="Open in Explorer">
                          <ExternalLink className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => handleOptimizeImage(file.path)} className="shrink-0 px-3 py-1.5 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 rounded-lg text-xs font-bold transition-all border border-emerald-500/20 hover:border-emerald-500/40">
                          Optimize
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : !mediaError ? (
                <div className="text-center py-8 text-xs text-slate-500 italic bg-black/20 rounded-xl border border-white/5">
                  No images found in the current workspace.
                </div>
              ) : null}
            </div>
          </div>
        );

      case 'advanced':
        return (
          <div className="p-8 grid grid-cols-2 gap-6 overflow-y-auto custom-scrollbar">
            <div className="col-span-2 mb-2">
              <h2 className="text-2xl font-bold flex items-center gap-3 text-violet-400">
                <Layers className="w-8 h-8" /> Advanced Tools
              </h2>
            </div>
            
            <div className="glass-card space-y-4">
              <div className="flex items-center gap-2 text-violet-400 font-bold">
                <Wand2 className="w-5 h-5" /> Regex Renamer
              </div>
              <div className="space-y-2">
                <input type="text" placeholder="Find pattern (regex)" value={regexPattern} onChange={e => setRegexPattern(e.target.value)} className="glass-input w-full text-xs font-mono"/>
                <input type="text" placeholder="Replacement" value={regexReplacement} onChange={e => setRegexReplacement(e.target.value)} className="glass-input w-full text-xs font-mono"/>
              </div>
              <button onClick={() => runOperation('advanced_regex_rename', regexPattern, regexReplacement)} className="w-full py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-xs font-bold transition-all">Apply Regex</button>
            </div>

            <div className="glass-card space-y-4">
              <div className="flex items-center gap-2 text-orange-400 font-bold">
                <Archive className="w-5 h-5" /> Old File Cleanup
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500">Older than</span>
                <input type="number" value={automationDays} onChange={e => setAutomationDays(Number(e.target.value))} className="glass-input w-24 py-1.5 text-xs text-orange-400 font-bold" />
                <span className="text-xs text-slate-500">days</span>
              </div>
              <button onClick={() => runOperation('cleanup_old_files', automationDays)} className="w-full py-2 bg-orange-600 hover:bg-orange-500 rounded-lg text-xs font-bold transition-all">Archive Old Files</button>
            </div>

            <div className="glass-card space-y-4">
              <div className="flex items-center gap-2 text-sky-400 font-bold">
                <PackageOpen className="w-5 h-5" /> Batch Extractor
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">Extract all archives (.zip, .rar, .7z) in workspace into matching folders.</p>
              <button onClick={() => runOperation('batch_unzip')} className="w-full py-2 bg-sky-600 hover:bg-sky-500 rounded-lg text-xs font-bold transition-all">Extract All</button>
            </div>

            <div className="glass-card space-y-4">
              <div className="flex items-center gap-2 text-teal-400 font-bold">
                <FolderSync className="w-5 h-5" /> Additive Backup
              </div>
              <div className="text-[10px] text-slate-500 flex items-center gap-2">
                <span className="truncate max-w-[100px]">{path || 'Source…'}</span>
                <MoveRight className="w-3 h-3" />
                <span className="truncate max-w-[100px] text-teal-400">{backupDest || 'Select Dest…'}</span>
              </div>
              <div className="flex gap-2">
                <button onClick={handleSelectBackupDest} className="flex-1 py-2 bg-slate-800 rounded-lg text-[10px] font-bold">Select Dest</button>
                <button onClick={() => runOperation('additive_backup', backupDest)} className="flex-[2] py-2 bg-teal-600 rounded-lg text-[10px] font-bold">Run Backup</button>
              </div>
            </div>
          </div>
        );

      case 'rules':
        return (
          <div className="p-8 max-w-3xl mx-auto space-y-6">
            <div className="glass-card">
               <div className="flex justify-between items-center mb-6">
                  <h2 className="text-2xl font-bold flex items-center gap-3">
                    <Pencil className="w-8 h-8 text-indigo-400" /> Custom Rules Editor
                  </h2>
                  <button onClick={handleSaveRules} className="btn-primary !bg-emerald-600 flex items-center gap-2">
                    <Save className="w-4 h-4" /> Save Rules
                  </button>
               </div>

               <div className="space-y-4">
                 <div className="grid grid-cols-3 gap-3">
                    <input type="text" placeholder="Folder Name" value={newRuleFolder} onChange={e => setNewRuleFolder(e.target.value)} className="bg-black/40 border border-slate-700/50 rounded-xl px-4 py-3 text-xs" />
                    <input type="text" placeholder="Extensions (csv)" value={newRuleExts} onChange={e => setNewRuleExts(e.target.value)} className="bg-black/40 border border-slate-700/50 rounded-xl px-4 py-3 text-xs" />
                    <input type="text" placeholder="Keywords (csv)" value={newRuleKeywords} onChange={e => setNewRuleKeywords(e.target.value)} className="bg-black/40 border border-slate-700/50 rounded-xl px-4 py-3 text-xs" />
                 </div>
                 <button onClick={handleAddRule} className="w-full py-3 border border-indigo-500/30 bg-indigo-500/5 text-indigo-400 rounded-xl text-xs font-bold uppercase tracking-widest hover:bg-indigo-500/10 transition-all">Add New Rule</button>
               </div>

               <div className="mt-8 space-y-2 max-h-[400px] overflow-y-auto custom-scrollbar pr-2">
                  {customRules.map((rule, idx) => (
                    <div key={idx} className="flex items-center gap-4 p-4 bg-white/5 border border-white/5 rounded-xl group">
                       <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center shrink-0">
                          <FolderOpen className="w-5 h-5 text-indigo-400" />
                       </div>
                       <div className="flex-1 min-w-0">
                          <div className="font-bold text-slate-200">/ {rule.folder}</div>
                          <div className="flex gap-2 mt-1">
                             {rule.extensions.map(ex => <span key={ex} className="text-[9px] font-mono text-slate-500 px-1.5 py-0.5 bg-black/40 rounded border border-white/5">{ex}</span>)}
                             {rule.keywords.map(kw => <span key={kw} className="text-[9px] text-indigo-300 px-1.5 py-0.5 bg-indigo-500/10 rounded">{kw}</span>)}
                          </div>
                       </div>
                       <button onClick={() => handleDeleteRule(idx)} className="p-2 text-slate-600 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100">
                          <Trash2 className="w-4 h-4" />
                       </button>
                    </div>
                  ))}
               </div>
            </div>
          </div>
        );

      case 'stats':
        return (
          <div className="p-8 space-y-8 overflow-y-auto custom-scrollbar">
            <h2 className="text-2xl font-bold flex items-center gap-3">
              <BarChart3 className="w-8 h-8 text-primary" /> Workspace Analytics
            </h2>
            {stats ? (
              <div className="grid grid-cols-2 gap-6">
                 <div className="glass-card">
                    <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-6">Type Distribution</h3>
                    <div className="space-y-4">
                       {Object.entries(stats.categories).sort((a,b) => b[1] - a[1]).map(([cat, size]) => (
                         <div key={cat} className="space-y-1">
                            <div className="flex justify-between text-xs">
                               <span className="text-slate-300">{cat}</span>
                               <span className="text-slate-500">{Math.round(size / 1024 / 1024)} MB</span>
                            </div>
                            <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                               <div className="h-full bg-primary" style={{ width: `${(size / stats.total_size) * 100}%` }} />
                            </div>
                         </div>
                       ))}
                    </div>
                 </div>
                 <div className="glass-card">
                    <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-6">File Counts</h3>
                    <div className="text-6xl font-bold text-primary">{stats.file_count}</div>
                    <div className="text-xs text-slate-500 mt-2">Total files scanned and indexed</div>
                    <div className="mt-8 p-4 bg-primary/5 rounded-xl border border-primary/20 text-xs text-slate-400 leading-relaxed italic">
                      Analytics are based on the latest scan of your workspace. Refresh to update data after massive operations.
                    </div>
                 </div>
              </div>
            ) : (
              <div className="glass-card text-center py-20 italic text-slate-600">Select a folder and analyze to see data.</div>
            )}
          </div>
        );

      default: return null;
    }
  };

  return (
    <div className="flex h-screen w-full bg-[#0a0f1e] text-slate-100 overflow-hidden font-sans">
      
      {/* ── Sidebar Navigation ── */}
      <aside className="w-72 border-r border-slate-800/60 bg-slate-950/40 backdrop-blur-xl flex flex-col shrink-0">
        <div className="p-8">
           <h1 className="text-2xl font-black bg-gradient-to-br from-white to-slate-500 bg-clip-text text-transparent flex items-center gap-3">
             <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center shadow-lg shadow-primary/20">
               <FolderSync className="w-5 h-5 text-white" />
             </div>
             Organizer <span className="text-xs font-medium text-slate-600 bg-slate-900 px-1.5 py-0.5 rounded ml-auto">V5</span>
           </h1>
        </div>

        <nav className="flex-1 overflow-y-auto px-4 py-2 space-y-8 custom-scrollbar">
           {['General', 'Organizer', 'Processing', 'System'].map(group => (
             <div key={group} className="space-y-2">
                <h3 className="px-4 text-[10px] font-black uppercase tracking-[0.2em] text-slate-600">{group}</h3>
                <div className="space-y-1">
                   {menuItems.filter(m => m.group === group).map(item => (
                     <button
                       key={item.id}
                       onClick={() => setActiveView(item.id)}
                       className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group ${activeView === item.id ? 'bg-primary/10 text-primary border border-primary/20' : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'}`}
                     >
                        <item.icon className={`w-5 h-5 ${activeView === item.id ? 'text-primary' : 'text-slate-500 group-hover:text-slate-300'}`} />
                        <span className="text-sm font-semibold">{item.label}</span>
                        {activeView === item.id && <ChevronRight className="w-4 h-4 ml-auto" />}
                     </button>
                   ))}
                </div>
             </div>
           ))}
        </nav>

        <div className="p-6 border-t border-slate-800/60">
           <div className="flex items-center gap-3 p-3 bg-slate-900/50 rounded-2xl border border-white/5">
              <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center">
                 <Settings className="w-5 h-5 text-slate-500" />
              </div>
              <div className="flex-1 min-w-0">
                 <div className="text-[10px] font-bold text-slate-200 truncate uppercase tracking-widest">NeoGiant</div>
                 <div className="text-[10px] text-slate-500 truncate">System Administrator</div>
              </div>
           </div>
        </div>
      </aside>

      {/* ── Workspace ── */}
      <main className="flex-1 flex flex-col min-w-0 relative bg-gradient-to-b from-transparent to-slate-950/20">
         {/* Top Header */}
         <header className="h-20 border-b border-slate-800/60 flex items-center justify-between px-8 shrink-0 bg-slate-950/20 backdrop-blur-md z-10">
            <div className="flex items-center gap-4">
               {hasHistory && (
                 <button
                   onClick={() => runOperation('undo_last_operation')}
                   className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl hover:bg-red-500/20 transition-all active:scale-95 shadow-lg shadow-red-500/5"
                 >
                   <Undo2 className="w-4 h-4" />
                   <span className="text-[10px] font-black uppercase tracking-widest leading-none">Restore Snapshot</span>
                 </button>
               )}
            </div>

            <div className="flex items-center gap-6">
              <div className="flex items-center gap-3 bg-slate-900/50 px-4 py-2 rounded-xl border border-slate-800/60">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Simulation</span>
                <button
                  onClick={() => setIsDryRun(!isDryRun)}
                  className={`w-10 h-5 rounded-full p-1 transition-all relative ${isDryRun ? 'bg-accent shadow-[0_0_10px_rgba(244,63,94,0.3)]' : 'bg-slate-700'}`}
                >
                  <div className={`w-3 h-3 bg-white rounded-full transition-transform duration-300 ${isDryRun ? 'translate-x-5' : 'translate-x-0'}`} />
                </button>
              </div>
              <button onClick={handleRefreshStats} className="p-2.5 text-slate-500 hover:text-white transition-colors bg-slate-900/50 border border-slate-800/60 rounded-xl">
                 <RefreshCw className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
              </button>
            </div>
         </header>

         {/* Content Area */}
         <div className="flex-1 relative overflow-hidden">
            {renderWorkspace()}
         </div>
      </main>

      {/* ── Utility & Status Rail ── */}
      <aside className="w-80 border-l border-slate-800/60 bg-slate-950/40 backdrop-blur-xl flex flex-col shrink-0">
        <div className="p-6 border-b border-slate-800/60">
           <h3 className="text-xs font-black uppercase tracking-[0.2em] text-slate-500 mb-4">Largest Assets</h3>
           <div className="space-y-2 max-h-[300px] overflow-y-auto custom-scrollbar pr-2">
              {stats?.top_files.map((file, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSelectFile(file)}
                  className="w-full text-left p-3 bg-white/5 border border-white/5 rounded-xl hover:bg-white/10 hover:border-primary/30 transition-all group"
                >
                  <div className="flex justify-between items-start gap-2">
                    <span className="text-[11px] font-bold truncate text-slate-300 group-hover:text-primary flex-1">{file.name}</span>
                    <span className="text-[10px] font-mono text-primary shrink-0">{file.size_str}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-[8px] text-slate-600 uppercase tracking-widest font-black">{file.type}</span>
                    <div className="flex-1 h-0.5 bg-slate-800 rounded-full overflow-hidden">
                       <div className="h-full bg-primary/40" style={{ width: '40%' }} />
                    </div>
                  </div>
                </button>
              ))}
              {!stats && <div className="text-center py-10 text-[10px] text-slate-700 italic">No assets indexed.</div>}
           </div>
        </div>

        {/* Engine Logs */}
        <div className="flex-1 flex flex-col min-h-0">
           <div className="px-6 py-4 border-b border-slate-800/60 flex justify-between items-center bg-black/20">
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Live Console</span>
              <button onClick={() => setLogs([])} className="text-[8px] text-slate-700 hover:text-slate-400 uppercase font-black">Flush</button>
           </div>
           <div className="flex-1 overflow-y-auto p-6 font-mono text-[10px] space-y-2 custom-scrollbar">
              {logs.map((log, i) => (
                <div key={i} className="flex gap-3 leading-relaxed">
                  <span className="text-slate-800 shrink-0 select-none">[{log.timestamp}]</span>
                  <span className={log.type === 'error' ? 'text-red-500' : log.type === 'success' ? 'text-emerald-400' : 'text-slate-400'}>
                    {log.message}
                  </span>
                </div>
              ))}
           </div>
        </div>
      </aside>

      {/* ── Asset Preview Overlay ── */}
      {sidebarOpen && selectedFile && (
        <div className="fixed inset-y-0 right-0 w-[400px] bg-slate-950 border-l border-white/10 shadow-[0_0_100px_rgba(0,0,0,0.8)] z-[150] p-10 flex flex-col animate-in slide-in-from-right duration-300">
           <div className="flex justify-between items-center mb-10">
              <h3 className="text-sm font-black uppercase tracking-[0.3em] text-primary">Metadata Insight</h3>
              <button onClick={() => setSidebarOpen(false)} className="w-10 h-10 rounded-full hover:bg-white/5 flex items-center justify-center transition-colors">
                <X className="w-6 h-6" />
              </button>
           </div>

           <div className="aspect-square glass-card bg-black border-white/5 flex items-center justify-center mb-10 overflow-hidden shadow-2xl">
              {['.jpg', '.jpeg', '.png', '.gif', '.webp'].includes(selectedFile.extension) ? (
                <img src={selectedFile.uri} className="w-full h-full object-contain p-4" alt={selectedFile.name} />
              ) : (
                <div className="flex flex-col items-center gap-4">
                   <FileType2 className="w-20 h-20 text-slate-800" />
                   <span className="text-[10px] font-bold text-slate-700 uppercase tracking-widest">{selectedFile.extension} File</span>
                </div>
              )}
           </div>

           <div className="flex-1 space-y-8 overflow-y-auto custom-scrollbar pr-2">
              <div className="space-y-1">
                 <div className="text-[9px] font-black uppercase tracking-widest text-slate-600">Full Filename</div>
                 <div className="text-sm text-slate-100 font-bold leading-snug break-all">{selectedFile.name}</div>
              </div>
              
              <div className="grid grid-cols-2 gap-8">
                 <div className="space-y-1">
                    <div className="text-[9px] font-black uppercase tracking-widest text-slate-600">Size</div>
                    <div className="text-sm text-primary font-mono">{selectedFile.size}</div>
                 </div>
                 <div className="space-y-1">
                    <div className="text-[9px] font-black uppercase tracking-widest text-slate-600">Type</div>
                    <div className="text-sm text-primary uppercase font-bold">{selectedFile.extension}</div>
                 </div>
              </div>

              <div className="space-y-1">
                 <div className="text-[9px] font-black uppercase tracking-widest text-slate-600">Last Transformation</div>
                 <div className="text-sm text-slate-400">{selectedFile.modified}</div>
              </div>

              <div className="pt-6 border-t border-white/5">
                 <button
                   onClick={() => { setPrefix(selectedFile.name.split('.')[0]); setSidebarOpen(false); setActiveView('renamer'); }}
                   className="w-full py-4 bg-primary/10 border border-primary/30 text-primary rounded-2xl text-[10px] font-black uppercase tracking-[0.2em] hover:bg-primary/20 transition-all active:scale-95"
                 >
                   Pass to Renamer
                 </button>
              </div>
           </div>
        </div>
      )}

      {/* ── Modals & Overlays ── */}
      {showSystemWarning && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-xl flex items-center justify-center z-[200] p-10">
          <div className="w-[500px] glass border-red-500/50 rounded-[2rem] p-12 shadow-[0_0_100px_rgba(239,68,68,0.2)] flex flex-col gap-8 text-center">
            <div className="mx-auto w-20 h-20 rounded-3xl bg-red-500/20 flex items-center justify-center">
              <ShieldAlert className="w-10 h-10 text-red-500" />
            </div>
            <div>
               <h2 className="text-2xl font-black text-white mb-4">Critical Protection Shield</h2>
               <p className="text-slate-400 text-sm leading-relaxed">
                 You have selected a <span className="text-red-500 font-bold underline">Root or System partition</span>. 
                 Proceeding here can lead to unrecoverable system failure. Do you have explicit clearance?
               </p>
            </div>
            <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-4 font-mono text-xs text-red-400 break-all">
              {pendingSystemPath}
            </div>
            <div className="flex gap-4">
              <button onClick={() => { setShowSystemWarning(false); setPendingSystemPath(''); }} className="flex-1 py-4 bg-slate-900 border border-white/10 text-slate-400 rounded-2xl text-xs font-black uppercase tracking-widest hover:bg-slate-800 transition-all">Abortion</button>
              <button onClick={handleConfirmSystemPath} className="flex-1 py-4 bg-red-600 text-white rounded-2xl text-xs font-black uppercase tracking-widest hover:bg-red-500 transition-all shadow-lg shadow-red-600/20">Manual Override</button>
            </div>
          </div>
        </div>
      )}

      {loading && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex flex-col items-center justify-center z-[300]">
          <div className="relative w-48 h-48">
            <svg className="w-full h-full transform -rotate-90">
              <circle cx="96" cy="96" r="88" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-slate-900" />
              <circle cx="96" cy="96" r="88" stroke="currentColor" strokeWidth="8" fill="transparent" strokeDasharray={552.92} strokeDashoffset={552.92 - (552.92 * progress) / 100} className="text-primary transition-all duration-300 ease-out" />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-4xl font-black text-white">{progress}%</span>
              <span className="text-[10px] font-black text-primary uppercase tracking-[0.2em] mt-1">Hashed</span>
            </div>
          </div>
          <p className="mt-10 text-[10px] font-black text-slate-500 tracking-[0.5em] uppercase animate-pulse">Neural Engine Processing</p>
        </div>
      )}
    </div>
  );
};

export default App;
