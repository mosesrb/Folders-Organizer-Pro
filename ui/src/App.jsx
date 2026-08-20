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
  ShieldCheck,
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
  FolderArchive,
  Sun,
  Moon,
} from 'lucide-react';

// App identity mark — a manila folder with a stamped checkmark, matching
// branding/logo-mark.svg exactly. Kept as its own fixed brand colors
// (cream folder, stamp-red circle) rather than currentColor/theme tokens,
// the same way most app logos stay visually consistent across light/dark
// themes rather than re-theming.
const LogoMark = ({ className }) => (
  <svg viewBox="0 0 512 512" className={className} xmlns="http://www.w3.org/2000/svg">
    <path d="M 106 168 Q 106 152 122 152 L 224 152 Q 234 152 240 160 L 258 184 L 388 184 Q 404 184 404 200 L 404 210 L 106 210 Z" fill="#E4D9C4"/>
    <rect x="96" y="196" width="320" height="184" rx="18" fill="#FBF8F1"/>
    <line x1="96" y1="196" x2="416" y2="196" stroke="#E4D9C4" strokeWidth="4"/>
    <g transform="rotate(-14 360 328)">
      <circle cx="360" cy="328" r="74" fill="#8A2E2E" stroke="#FBF8F1" strokeWidth="7"/>
      <path d="M 322 330 L 348 356 L 400 300" fill="none" stroke="#FBF8F1" strokeWidth="15" strokeLinecap="round" strokeLinejoin="round"/>
    </g>
  </svg>
);

const App = () => {
  // — Core state —
  const [path, setPath] = useState('');
  const [prefix, setPrefix] = useState('Item_');
  const [oldExt, setOldExt] = useState('.zip');
  const [newExt, setNewExt] = useState('.cbr');
  const [sortMode, setSortMode] = useState('name');
  const [isDryRun, setIsDryRun] = useState(false);
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('organizer-theme');
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });
  const [recursiveMode, setRecursiveMode] = useState(false); // "include subfolders" — applies to ops that support it (see RECURSIVE_CAPABLE_OPS)
  const [filterText, setFilterText] = useState('');
  const [status, setStatus] = useState({ type: '', message: '' });
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  const [hasHistory, setHasHistory] = useState(false);
  const [useRegex, setUseRegex] = useState(false);
  const [dateGrain, setDateGrain] = useState('month');
  const [duplicates, setDuplicates] = useState([]);
  const [previewItems, setPreviewItems] = useState(null); // { opTitle, items: [{src,dst}] } from the most recent dry run
  const [keepBy, setKeepBy] = useState('oldest'); // which file in a duplicate group to keep: oldest | newest | shortest_path
  const [confirmDialog, setConfirmDialog] = useState(null); // { title, message, onConfirm } — generic confirm gate for destructive ops
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
  const [largeFileThresholdMb, setLargeFileThresholdMb] = useState(500);
  const [automationThresholdMb, setAutomationThresholdMb] = useState(500);
  const [regexPattern, setRegexPattern] = useState('');
  const [regexReplacement, setRegexReplacement] = useState('');
  const [backupDest, setBackupDest] = useState('');
  const [imgSourceExts, setImgSourceExts] = useState('.png,.bmp');
  const [imgTargetExt, setImgTargetExt] = useState('.webp');
  const [zipFolders, setZipFolders] = useState([]); // [{name, item_count, size_str}]
  const [zipSelected, setZipSelected] = useState([]); // folder names checked
  const [zipTargetExt, setZipTargetExt] = useState('.zip');
  const [zipDeleteOriginals, setZipDeleteOriginals] = useState(false);

  // — Privacy Policy & Terms state —
  const [hasAcceptedTerms, setHasAcceptedTerms] = useState(() => {
    return localStorage.getItem('organizer-terms-accepted') === 'true';
  });
  const [showTermsModal, setShowTermsModal] = useState(!hasAcceptedTerms);
  const [termsTab, setTermsTab] = useState('privacy'); // 'privacy' | 'terms'

  const handleAcceptTerms = () => {
    localStorage.setItem('organizer-terms-accepted', 'true');
    setHasAcceptedTerms(true);
    setShowTermsModal(false);
  };

  // — Progress listener —
  useEffect(() => {
    const handleProgress = (e) => setProgress(e.detail);
    window.addEventListener('progressUpdate', handleProgress);
    return () => window.removeEventListener('progressUpdate', handleProgress);
  }, []);

  // — Theme —
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('organizer-theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'));

  // — Auto-load stats + rules when path changes —
  useEffect(() => {
    if (path) {
      refreshStats();
      loadRules();
      refreshMediaFiles();
      loadZipFolders();
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

  const loadZipFolders = async () => {
    if (!path || !window.pywebview?.api) return;
    const res = await window.pywebview.api.list_subfolders(path);
    if (res.success) {
      setZipFolders(res.folders);
      setZipSelected((prev) => prev.filter((n) => res.folders.some((f) => f.name === n)));
    }
  };

  const toggleZipSelected = (name) => {
    setZipSelected((prev) => prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]);
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
        const result = await window.pywebview.api.select_folder('workspace');
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
        const result = await window.pywebview.api.select_folder('backup');
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

  const handleFindDuplicates = async () => {
    if (!path || !window.pywebview?.api) {
      showStatus('error', 'Please select a path first');
      return;
    }
    setLoading(true);
    setProgress(0);
    addLog('Scanning for duplicates (size → head hash → full hash)...', 'info');
    const res = await window.pywebview.api.find_duplicates(path, null, keepBy);
    setLoading(false);
    setProgress(0);
    if (res.success) {
      setDuplicates(res.duplicates || []);
      showStatus('info', res.message);
    } else {
      showStatus('error', res.error);
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
    'batch_zip_folders', 'change_extensions',
  ];

  // Operations that permanently change/delete files on disk and are NOT
  // gated by the system-critical-directory modal. Previously these fired
  // immediately with no "are you sure?" step whenever Dry Run was off —
  // the only safety net was remembering to toggle Dry Run first.
  const DESTRUCTIVE_OPS = [
    'delete_duplicates', 'cleanup_old_files', 'advanced_regex_rename',
    'flatten_workspace', 'archive_large_files', 'change_extensions', 'batch_unzip',
    'batch_zip_folders',
  ];

  const opTitleFor = (opName) => opName
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

  // Operations whose backend signature accepts a trailing `recursive` bool
  const RECURSIVE_CAPABLE_OPS = [
    'advanced_regex_rename', 'cleanup_old_files', 'archive_large_files',
    'batch_unzip', 'change_extensions', 'convert_image_formats',
  ];

  const executeOperation = async (opName, ...args) => {
    let finalArgs = [...args];
    if (opName === 'sequential_rename') {
      finalArgs = [prefix, 'files', sortMode, isDryRun, filterText, useRegex];
    } else if (opName === 'change_extensions') {
      finalArgs = [oldExt, newExt, isDryRun, filterText, recursiveMode];
    } else if (opName === 'delete_duplicates') {
      finalArgs = [duplicates, isDryRun, keepBy];
    } else if (opName === 'sort_by_date') {
      finalArgs = [dateGrain, isDryRun];
    } else if (opName === 'smart_categorize') {
      finalArgs = [isDryRun, customRules];
    } else if (RECURSIVE_CAPABLE_OPS.includes(opName)) {
      finalArgs = [...args, isDryRun, recursiveMode];
    } else {
      finalArgs = [...args, isDryRun];
    }

    const opTitle = opTitleFor(opName);

    addLog(`${isDryRun ? '[SIMULATION] ' : ''}Starting ${opTitle}...`, 'info');
    setLoading(true);
    setProgress(0);

    try {
      if (window.pywebview && window.pywebview.api) {
        const result = await window.pywebview.api[opName](path, ...finalArgs);

        if (result.success) {
          showStatus(isDryRun ? 'info' : 'success', result.message);
          if (result.errors && result.errors.length > 0) {
            result.errors.forEach(err => addLog(err, 'error'));
          }
          if (result.history_warning) {
            addLog(`⚠ ${result.history_warning}`, 'error');
          }
          if (isDryRun && Array.isArray(result.items) && result.items.length > 0) {
            setPreviewItems({ opTitle, items: result.items });
          } else if (!isDryRun) {
            setPreviewItems(null);
          }
          if (UNDOABLE_OPS.includes(opName) && !isDryRun) setHasHistory(true);
          if (opName === 'undo_last_operation') setHasHistory(false);
          if (opName === 'find_duplicates') setDuplicates(result.duplicates || []);
          if (opName === 'delete_duplicates') setDuplicates([]);
          refreshStats();
          if (opName === 'batch_zip_folders') loadZipFolders();
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

  const runOperation = async (opName, ...args) => {
    if (!path) {
      showStatus('error', 'Please select a path first');
      return;
    }

    if (DESTRUCTIVE_OPS.includes(opName) && !isDryRun) {
      const opTitle = opTitleFor(opName);
      setConfirmDialog({
        title: `Confirm: ${opTitle}`,
        message: `This will modify or delete files on disk now (Dry Run is off). ${
          opName === 'delete_duplicates'
            ? `Non-kept copies in each group will be sent to the Recycle Bin.`
            : `This action can only be reversed with the Undo button, and only if it completed successfully.`
        }`,
        onConfirm: () => { setConfirmDialog(null); executeOperation(opName, ...args); },
      });
      return;
    }

    return executeOperation(opName, ...args);
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
    { id: 'duplicates', label: 'Duplicates', icon: Copy, group: 'Organizer' },
    { id: 'media', label: 'Media Tools', icon: Music, group: 'Processing' },
    { id: 'advanced', label: 'Advanced Tools', icon: Layers, group: 'Processing' },
    { id: 'rules', label: 'Custom Rules', icon: Pencil, group: 'System' },
    { id: 'stats', label: 'Analytics', icon: BarChart3, group: 'System' },
  ];

  const renderWorkspace = () => {
    switch (activeView) {
      case 'dashboard':
        return (
          <div className="absolute inset-0 overflow-y-auto custom-scrollbar grid grid-cols-2 gap-6 p-8">
            <div className="col-span-2 glass-card border-primary/20 bg-primary/5">
              <h2 className="text-xl font-bold flex items-center gap-3 mb-3 text-primary">
                <FolderOpen className="w-6 h-6" /> Workspace Status
              </h2>
              <div className="flex gap-4 items-center">
                <div className="flex-1 bg-secondary/70 border border-slate-300 rounded-xl px-4 py-2.5 text-ink font-mono text-xs truncate">
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
                  <div className="text-3xl font-bold text-ink">{stats.total_size_str}</div>
                  <div className="text-[10px] text-slate-600">Current active directory volume</div>
                </div>
                <div className="glass-card flex flex-col gap-2">
                  <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Categories</span>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {Object.entries(stats.categories).map(([cat, size]) => (
                      <div key={cat} className="px-2 py-1 bg-secondary/60 rounded-lg text-[10px] border border-slate-300">
                        <span className="text-ink-soft">{cat}:</span> <span className="text-primary font-bold">{Math.round(size / 1024 / 1024)}MB</span>
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
               <button onClick={() => setActiveView('media')} className="p-6 glass-card border-pink-500/20 hover:bg-pink-500/5 flex flex-col items-center gap-3 text-center">
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
          <div className="absolute inset-0 overflow-y-auto custom-scrollbar p-8 max-w-2xl mx-auto space-y-8">
            <div className="glass-card border-indigo-500/20 bg-indigo-500/5">
              <h2 className="text-2xl font-bold flex items-center gap-3 mb-6">
                <Wand2 className="w-8 h-8 text-indigo-400" /> Smart Categorizer
              </h2>
              <div className="space-y-6">
                <p className="text-sm text-ink-soft leading-relaxed">
                  Automatically sort files into folders based on their extensions and keywords using the rules defined in the 
                  <button onClick={() => setActiveView('rules')} className="text-indigo-400 font-bold hover:underline mx-1">Rules Editor</button>.
                </p>
                
                <div className="p-4 bg-secondary/70 border border-slate-300 rounded-xl space-y-3">
                   <div className="text-[10px] font-black uppercase tracking-widest text-slate-500">Active Rules: {customRules.length}</div>
                   <div className="flex flex-wrap gap-2">
                      {customRules.slice(0, 5).map((r, i) => (
                        <span key={i} className="px-2 py-1 bg-indigo-500/10 border border-indigo-500/20 text-indigo-700 text-[10px] rounded-lg">/{r.folder}</span>
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
          <div className="absolute inset-0 overflow-y-auto custom-scrollbar p-8 max-w-2xl mx-auto space-y-8">
            <div className="glass-card border-orange-500/20 bg-orange-500/5">
              <h2 className="text-2xl font-bold flex items-center gap-3 mb-6">
                <CalendarClock className="w-8 h-8 text-orange-400" /> Date-Based Organizer
              </h2>
              <div className="space-y-8">
                <p className="text-sm text-ink-soft leading-relaxed">
                  Organize your files into a chronological folder structure based on their last modification date.
                </p>

                <div className="space-y-4">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block px-1">Grouping Granularity</label>
                  <div className="grid grid-cols-3 gap-3">
                    {['year', 'month', 'day'].map(grain => (
                      <button 
                        key={grain}
                        onClick={() => setDateGrain(grain)}
                        className={`py-3 rounded-xl border text-xs font-bold uppercase transition-all ${dateGrain === grain ? 'bg-orange-500/20 border-orange-500/50 text-orange-600' : 'bg-secondary/40 border-slate-300 text-slate-600 hover:bg-secondary'}`}
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

      case 'duplicates':
        return (
          <div className="absolute inset-0 overflow-y-auto custom-scrollbar p-8 max-w-3xl mx-auto space-y-6">
            <div className="glass-card border-pink-500/20 bg-pink-500/5">
              <h2 className="text-2xl font-bold flex items-center gap-3 mb-4">
                <Copy className="w-8 h-8 text-pink-400" /> Duplicate Finder
              </h2>
              <p className="text-sm text-ink-soft leading-relaxed mb-6">
                Scans recursively and compares files by content (size → 1KB header hash → full hash), not just filename.
              </p>

              <div className="space-y-3 mb-6">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block px-1">
                  Which copy should be kept in each group?
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { id: 'oldest', label: 'Oldest' },
                    { id: 'newest', label: 'Newest' },
                    { id: 'shortest_path', label: 'Shallowest Path' },
                  ].map(opt => (
                    <button
                      key={opt.id}
                      aria-pressed={keepBy === opt.id}
                      onClick={() => setKeepBy(opt.id)}
                      className={`py-3 rounded-xl border text-xs font-bold uppercase transition-all ${keepBy === opt.id ? 'bg-pink-500/20 border-pink-500/50 text-pink-700' : 'bg-secondary/40 border-slate-300 text-slate-600 hover:bg-secondary'}`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={handleFindDuplicates}
                aria-label="Scan workspace for duplicate files"
                className="w-full btn-primary !bg-pink-600 hover:!bg-pink-500 py-4 text-lg font-bold flex items-center justify-center gap-2"
              >
                <FileSearch className="w-5 h-5" /> Scan for Duplicates
              </button>
            </div>

            {duplicates.length > 0 && (
              <div className="glass-card">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold text-ink">
                    {duplicates.length} duplicate group{duplicates.length !== 1 ? 's' : ''} found
                  </h3>
                  <button
                    onClick={() => runOperation('delete_duplicates')}
                    aria-label="Send all non-kept duplicate copies to the Recycle Bin"
                    className="px-4 py-2 bg-red-600/80 hover:bg-red-500 rounded-lg text-xs font-bold flex items-center gap-2"
                  >
                    <Trash2 className="w-4 h-4" /> {isDryRun ? 'Simulate Cleanup' : 'Send Extras to Recycle Bin'}
                  </button>
                </div>
                <div className="space-y-3 max-h-[420px] overflow-y-auto custom-scrollbar pr-2">
                  {duplicates.map((group, gIdx) => (
                    <div key={gIdx} className="bg-secondary/40 border border-slate-200 rounded-xl p-4 space-y-2">
                      {group.map((filePath, fIdx) => (
                        <div key={fIdx} className={`flex items-center gap-2 text-xs font-mono truncate ${fIdx === 0 ? 'text-emerald-400' : 'text-slate-500 line-through decoration-red-500/50'}`}>
                          <span className={`shrink-0 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${fIdx === 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                            {fIdx === 0 ? 'Keep' : 'Remove'}
                          </span>
                          <span className="truncate">{filePath}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );

      case 'renamer':
        return (
          <div className="absolute inset-0 overflow-y-auto custom-scrollbar p-8 max-w-2xl mx-auto space-y-8">
            <div className="glass-card">
              <h2 className="text-2xl font-bold flex items-center gap-3 mb-6">
                <Hash className="w-8 h-8 text-accent" /> Sequential Renamer
              </h2>
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-ink-soft">Sorting Priority</span>
                  <div className="flex bg-secondary/50 rounded-xl p-1 border border-slate-300">
                    <button onClick={() => setSortMode('name')} className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all ${sortMode === 'name' ? 'bg-primary text-on-primary' : 'text-slate-600'}`}>NAME</button>
                    <button onClick={() => setSortMode('date')} className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all ${sortMode === 'date' ? 'bg-primary text-on-primary' : 'text-slate-600'}`}>DATE</button>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <div className="flex justify-between items-center px-1">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Naming Pattern</label>
                    <button onClick={() => setUseRegex(!useRegex)} className={`px-2 py-0.5 text-[9px] font-bold rounded border ${useRegex ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-700' : 'bg-secondary/50 border-slate-300 text-slate-600'}`}>REGEX MODE</button>
                  </div>
                  <input type="text" value={prefix} onChange={(e) => setPrefix(e.target.value)} className="glass-input w-full" placeholder="Enter prefix (e.g. Photo_)" />
                </div>

                <div className="flex gap-4">
                   <button onClick={() => runOperation('sequential_rename')} className="btn-primary flex-1 py-4">Rename Files</button>
                   <button onClick={() => runOperation('sequential_rename', prefix, 'folders')} className="btn-ghost flex-1 py-4">Rename Folders</button>
                </div>
              </div>
            </div>

            <div className="glass-card border-slate-300">
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
          <div className="absolute inset-0 overflow-y-auto custom-scrollbar p-8 max-w-2xl mx-auto space-y-8">
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
                <label className="flex items-center justify-center gap-2 text-xs text-cyan-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={recursiveMode}
                    onChange={(e) => setRecursiveMode(e.target.checked)}
                    className="accent-cyan-500"
                    aria-label="Include subfolders"
                  />
                  Include subfolders
                </label>
              </div>
            </div>
          </div>
        );

      case 'media':
        return (
          <div className="absolute inset-0 overflow-y-auto custom-scrollbar p-8 grid grid-cols-2 gap-6">
            <div className="col-span-2 mb-2">
              <h2 className="text-2xl font-bold flex items-center gap-3">
                <Music className="w-8 h-8 text-pink-400" /> Media Processing Hub
              </h2>
              <p className="text-ink-soft mt-1">Professional optimization tools for audio, documents, and imagery.</p>
            </div>

            <div className="col-span-2 glass-card border-pink-500/20 bg-pink-500/5 flex flex-col gap-4">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-pink-500/20 flex items-center justify-center shrink-0">
                    <Music className="w-5 h-5 text-pink-400" />
                  </div>
                  <div>
                    <h3 className="font-bold text-ink">MP3 to WAV Converter</h3>
                    <p className="text-xs text-slate-500">Convert audio files losslessly. {audioFiles.length} file(s) found.</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <button onClick={refreshMediaFiles} className="btn-ghost py-2 px-4 flex items-center justify-center gap-2 text-xs shrink-0 border border-slate-700">
                    <RotateCcw className="w-4 h-4" /> Refresh
                  </button>
                  <label className="flex items-center gap-2 text-xs text-pink-700 cursor-pointer">
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
                    <div key={idx} className="flex justify-between items-center p-3 bg-secondary/70 rounded-xl border border-slate-200 hover:border-pink-500/20 transition-all">
                      <div className="flex items-center gap-3 overflow-hidden">
                        <Music className="w-4 h-4 text-pink-400 shrink-0" />
                        <span className="text-xs truncate text-ink-soft" title={file.name}>{file.name}</span>
                        <span className="text-[10px] text-slate-500 shrink-0 bg-secondary/70 px-2 py-0.5 rounded">{file.size}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => handleOpenInExplorer(file.path)} aria-label={`Open ${file.name} in Explorer`} className="shrink-0 p-1.5 text-slate-500 hover:text-pink-400 transition-colors" title="Open in Explorer">
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
                <div className="text-center py-8 text-xs text-slate-500 italic bg-secondary/30 rounded-xl border border-slate-200">
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
                    <h3 className="font-bold text-ink">PDF Compressor</h3>
                    <p className="text-xs text-slate-500">Reduce PDF file size. {pdfFiles.length} file(s) found.</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <button onClick={refreshMediaFiles} className="btn-ghost py-2 px-4 flex items-center justify-center gap-2 text-xs shrink-0 border border-slate-700">
                    <RotateCcw className="w-4 h-4" /> Refresh
                  </button>
                  <label className="flex items-center gap-2 text-xs text-red-600 cursor-pointer">
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
                    <div key={idx} className="flex justify-between items-center p-3 bg-secondary/70 rounded-xl border border-slate-200 hover:border-red-500/20 transition-all">
                      <div className="flex items-center gap-3 overflow-hidden">
                        <FileJson className="w-4 h-4 text-red-400 shrink-0" />
                        <span className="text-xs truncate text-ink-soft" title={file.name}>{file.name}</span>
                        <span className="text-[10px] text-slate-500 shrink-0 bg-secondary/70 px-2 py-0.5 rounded">{file.size}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => handleOpenInExplorer(file.path)} aria-label={`Open ${file.name} in Explorer`} className="shrink-0 p-1.5 text-slate-500 hover:text-red-400 transition-colors" title="Open in Explorer">
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
                <div className="text-center py-8 text-xs text-slate-500 italic bg-secondary/30 rounded-xl border border-slate-200">
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
                    <h3 className="font-bold text-ink">Image Optimizer</h3>
                    <p className="text-xs text-slate-500">Batch optimize images. {imageFiles.length} file(s) found.</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="flex flex-col items-end gap-1 mr-4">
                    <span className="text-[10px] font-bold text-slate-500 uppercase">Quality: {imgQuality}%</span>
                    <input type="range" min="10" max="100" value={imgQuality} onChange={(e) => setImgQuality(Number(e.target.value))} aria-label={`Image quality: ${imgQuality}%`} className="w-24 accent-emerald-500" />
                  </div>
                  <button onClick={refreshMediaFiles} className="btn-ghost py-2 px-4 flex items-center justify-center gap-2 text-xs shrink-0 border border-slate-700">
                    <RotateCcw className="w-4 h-4" /> Refresh
                  </button>
                  <label className="flex items-center gap-2 text-xs text-emerald-700 cursor-pointer">
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
                    <div key={idx} className="flex justify-between items-center p-3 bg-secondary/70 rounded-xl border border-slate-200 hover:border-emerald-500/20 transition-all">
                      <div className="flex items-center gap-3 overflow-hidden">
                        <ImageIcon className="w-4 h-4 text-emerald-400 shrink-0" />
                        <span className="text-xs truncate text-ink-soft" title={file.name}>{file.name}</span>
                        <span className="text-[10px] text-slate-500 shrink-0 bg-secondary/70 px-2 py-0.5 rounded">{file.size}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => handleOpenInExplorer(file.path)} aria-label={`Open ${file.name} in Explorer`} className="shrink-0 p-1.5 text-slate-500 hover:text-emerald-400 transition-colors" title="Open in Explorer">
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
                <div className="text-center py-8 text-xs text-slate-500 italic bg-secondary/30 rounded-xl border border-slate-200">
                  No images found in the current workspace.
                </div>
              ) : null}
            </div>
          </div>
        );

      case 'advanced':
        return (
          <div className="absolute inset-0 overflow-y-auto custom-scrollbar p-8 grid grid-cols-2 gap-6">
            <div className="col-span-2 mb-2 flex items-center justify-between flex-wrap gap-3">
              <h2 className="text-2xl font-bold flex items-center gap-3 text-violet-400">
                <Layers className="w-8 h-8" /> Advanced Tools
              </h2>
              <label className="flex items-center gap-2 text-xs text-violet-700 cursor-pointer bg-violet-500/10 border border-violet-500/20 rounded-xl px-4 py-2">
                <input
                  type="checkbox"
                  checked={recursiveMode}
                  onChange={(e) => setRecursiveMode(e.target.checked)}
                  className="accent-violet-500"
                  aria-label="Include subfolders for the tools below"
                />
                Include subfolders (applies to all tools below)
              </label>
            </div>
            
            <div className="col-span-2 glass-card space-y-4 border-primary/30">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-2 text-primary font-bold">
                  <FolderArchive className="w-5 h-5" /> Batch Folder Zipper
                </div>
                <button onClick={loadZipFolders} className="text-[10px] font-bold text-slate-500 hover:text-primary flex items-center gap-1">
                  <RefreshCw className="w-3 h-3" /> Refresh list
                </button>
              </div>
              <p className="text-xs text-ink-soft leading-relaxed">
                Select several top-level folders and zip each one into its own archive in a single pass — hand it a custom extension (e.g. <span className="font-mono text-primary">.cbz</span> for comic pages, <span className="font-mono text-primary">.bak</span> for a disguised backup) to fold "zip" and "change extension" into one step, instead of two.
              </p>

              <div className="border border-slate-300 rounded-xl max-h-52 overflow-y-auto custom-scrollbar divide-y divide-slate-200 bg-secondary/30">
                {zipFolders.length === 0 && (
                  <div className="text-center py-8 text-xs text-slate-600 italic">No subfolders found in this workspace.</div>
                )}
                {zipFolders.map((f) => (
                  <label key={f.name} className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-secondary/50 transition-colors">
                    <input type="checkbox" checked={zipSelected.includes(f.name)} onChange={() => toggleZipSelected(f.name)} className="accent-primary w-4 h-4" />
                    <span className="flex-1 text-xs font-bold text-ink truncate">{f.name}</span>
                    <span className="text-[10px] text-slate-500 shrink-0">{f.item_count} item{f.item_count !== 1 ? 's' : ''}</span>
                    <span className="text-[10px] font-mono text-primary w-16 text-right shrink-0">{f.size_str}</span>
                  </label>
                ))}
              </div>

              <div className="flex flex-wrap items-end gap-4">
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Archive extension</span>
                  <input type="text" value={zipTargetExt} onChange={(e) => setZipTargetExt(e.target.value)} placeholder=".zip" className="glass-input w-28 py-1.5 text-xs font-mono" />
                </div>
                <label className="flex items-center gap-2 text-xs text-ink-soft cursor-pointer bg-secondary/40 border border-slate-300 rounded-xl px-3 py-2">
                  <input type="checkbox" checked={zipDeleteOriginals} onChange={(e) => setZipDeleteOriginals(e.target.checked)} className="accent-accent" />
                  Send originals to Recycle Bin after zipping
                </label>
                <button
                  onClick={() => runOperation('batch_zip_folders', zipSelected, zipTargetExt, zipDeleteOriginals)}
                  disabled={zipSelected.length === 0}
                  className="ml-auto btn-primary flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <FolderArchive className="w-4 h-4" /> Zip {zipSelected.length || ''} Folder{zipSelected.length !== 1 ? 's' : ''}
                </button>
              </div>
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
              <div className="flex items-center gap-2 text-amber-400 font-bold">
                <Archive className="w-5 h-5" /> Large File Archiver
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500">Larger than</span>
                <input type="number" value={largeFileThresholdMb} onChange={e => setLargeFileThresholdMb(Number(e.target.value))} className="glass-input w-24 py-1.5 text-xs text-amber-400 font-bold" />
                <span className="text-xs text-slate-500">MB</span>
              </div>
              <button onClick={() => runOperation('archive_large_files', largeFileThresholdMb)} className="w-full py-2 bg-amber-600 hover:bg-amber-500 rounded-lg text-xs font-bold transition-all">Move to LargeFiles/</button>
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
                <button onClick={handleSelectBackupDest} className="flex-1 py-2 bg-secondary border border-slate-300 text-ink rounded-lg text-[10px] font-bold hover:bg-slate-200 transition-colors">Select Dest</button>
                <button onClick={() => runOperation('additive_backup', backupDest)} className="flex-[2] py-2 bg-filed text-on-filed rounded-lg text-[10px] font-bold hover:bg-filed-dark transition-colors">Run Backup</button>
              </div>
            </div>
          </div>
        );

      case 'rules':
        return (
          <div className="absolute inset-0 overflow-y-auto custom-scrollbar p-8 max-w-3xl mx-auto space-y-6">
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
                    <input type="text" placeholder="Folder Name" value={newRuleFolder} onChange={e => setNewRuleFolder(e.target.value)} className="glass-input text-xs" />
                    <input type="text" placeholder="Extensions (csv)" value={newRuleExts} onChange={e => setNewRuleExts(e.target.value)} className="glass-input text-xs" />
                    <input type="text" placeholder="Keywords (csv)" value={newRuleKeywords} onChange={e => setNewRuleKeywords(e.target.value)} className="glass-input text-xs" />
                 </div>
                 <button onClick={handleAddRule} className="w-full py-3 border border-indigo-500/30 bg-indigo-500/5 text-indigo-400 rounded-xl text-xs font-bold uppercase tracking-widest hover:bg-indigo-500/10 transition-all">Add New Rule</button>
               </div>

               <div className="mt-8 space-y-2 max-h-[400px] overflow-y-auto custom-scrollbar pr-2">
                  {customRules.map((rule, idx) => (
                    <div key={idx} className="flex items-center gap-4 p-4 bg-secondary/40 border border-slate-200 rounded-xl group">
                       <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center shrink-0">
                          <FolderOpen className="w-5 h-5 text-indigo-400" />
                       </div>
                       <div className="flex-1 min-w-0">
                          <div className="font-bold text-ink">/ {rule.folder}</div>
                          <div className="flex gap-2 mt-1">
                             {rule.extensions.map(ex => <span key={ex} className="text-[9px] font-mono text-slate-500 px-1.5 py-0.5 bg-secondary/70 rounded border border-slate-200">{ex}</span>)}
                             {rule.keywords.map(kw => <span key={kw} className="text-[9px] text-indigo-700 px-1.5 py-0.5 bg-indigo-500/10 rounded">{kw}</span>)}
                          </div>
                       </div>
                       <button onClick={() => handleDeleteRule(idx)} aria-label="Delete this rule" className="p-2 text-slate-600 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100">
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
          <div className="absolute inset-0 overflow-y-auto custom-scrollbar p-8 space-y-8">
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
                               <span className="text-ink-soft">{cat}</span>
                               <span className="text-slate-500">{Math.round(size / 1024 / 1024)} MB</span>
                            </div>
                            <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden">
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
                    <div className="mt-8 p-4 bg-primary/5 rounded-xl border border-primary/20 text-xs text-ink-soft leading-relaxed italic">
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
    <div className="flex h-screen w-full bg-background text-ink overflow-hidden font-sans">
      
      {/* ── Sidebar Navigation ── */}
      <aside className="w-64 border-r border-slate-300 bg-secondary/50 flex flex-col shrink-0">
        <div className="p-8">
           <h1 className="text-2xl font-bold font-serif text-ink flex items-center gap-3">
             <div className="w-8 h-8 bg-primary rounded-md flex items-center justify-center overflow-hidden shrink-0">
               <LogoMark className="w-7 h-7" />
             </div>
             Organizer <span className="text-xs font-medium text-slate-600 bg-slate-200 border border-slate-300 px-1.5 py-0.5 rounded ml-auto font-sans">V5</span>
           </h1>
        </div>

        <nav className="flex-1 overflow-y-auto px-4 py-2 space-y-6 custom-scrollbar">
           {['General', 'Organizer', 'Processing', 'System'].map(group => (
             <div key={group} className="space-y-2">
                <h3 className="px-4 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">{group}</h3>
                <div className="space-y-1">
                   {menuItems.filter(m => m.group === group).map(item => (
                     <button
                       key={item.id}
                       onClick={() => setActiveView(item.id)}
                       aria-current={activeView === item.id ? 'page' : undefined}
                       className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-md transition-all duration-200 group ${activeView === item.id ? 'bg-card text-primary border border-slate-300 border-r-0' : 'text-slate-600 hover:bg-slate-200/60 hover:text-ink border border-transparent'}`}
                     >
                        <item.icon className={`w-5 h-5 ${activeView === item.id ? 'text-primary' : 'text-slate-500 group-hover:text-slate-600'}`} aria-hidden="true" />
                        <span className="text-sm font-semibold">{item.label}</span>
                        {activeView === item.id && <ChevronRight className="w-4 h-4 ml-auto" />}
                     </button>
                   ))}
                </div>
             </div>
           ))}
        </nav>

        <div className="p-4 border-t border-slate-300 space-y-2">
           <div className="flex items-center gap-3 p-3 bg-card rounded-md border border-slate-300">
              <div className="w-10 h-10 rounded-full bg-slate-200 border border-slate-300 flex items-center justify-center">
                 <Settings className="w-5 h-5 text-slate-500" />
              </div>
              <div className="flex-1 min-w-0">
                 <div className="text-[10px] font-bold text-ink truncate uppercase tracking-widest">Folders Organizer Pro</div>
                 <div className="text-[10px] text-slate-500 truncate">Local desktop build · v5.0.4</div>
              </div>
              <button
                onClick={toggleTheme}
                aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                className="w-9 h-9 shrink-0 rounded-full border border-slate-300 hover:border-primary/50 hover:bg-secondary/60 flex items-center justify-center transition-colors"
              >
                {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-500" /> : <Moon className="w-4 h-4 text-slate-600" />}
              </button>
           </div>

           <button
             onClick={() => { setTermsTab('privacy'); setShowTermsModal(true); }}
             aria-label="View Privacy Policy and Terms of Use"
             className="w-full py-2 px-3 flex items-center justify-center gap-2 text-[10px] font-bold uppercase tracking-wider text-slate-600 hover:text-ink bg-secondary/50 hover:bg-secondary border border-slate-300 rounded-md transition-colors"
           >
             <ShieldCheck className="w-3.5 h-3.5 text-primary" />
             <span>Privacy & Terms</span>
           </button>
        </div>
      </aside>

      {/* ── Workspace ── */}
      <main className="flex-1 flex flex-col min-w-0 relative">
         {/* Top Header */}
         <header className="h-20 border-b border-slate-300 flex items-center justify-between px-8 shrink-0 bg-background z-10">
            <div className="flex items-center gap-4">
               {hasHistory && (
                 <button
                   onClick={() => runOperation('undo_last_operation')}
                   className="flex items-center gap-2 px-4 py-2 bg-accent/10 border border-accent/30 text-accent rounded-md hover:bg-accent/20 transition-all active:scale-95"
                 >
                   <Undo2 className="w-4 h-4" />
                   <span className="text-[10px] font-black uppercase tracking-widest leading-none">Restore Snapshot</span>
                 </button>
               )}
            </div>

            <div className="flex items-center gap-6">
              <div className="flex items-center gap-3 bg-card px-4 py-2 rounded-md border border-slate-300">
                <span id="dry-run-label" className="text-[10px] font-black uppercase tracking-widest text-slate-500">Simulation</span>
                <button
                  onClick={() => setIsDryRun(!isDryRun)}
                  role="switch"
                  aria-checked={isDryRun}
                  aria-labelledby="dry-run-label"
                  className={`w-10 h-5 rounded-full p-1 transition-all relative ${isDryRun ? 'bg-filed' : 'bg-slate-700'}`}
                >
                  <div className={`w-3 h-3 bg-white rounded-full transition-transform duration-300 ${isDryRun ? 'translate-x-5' : 'translate-x-0'}`} />
                </button>
              </div>
              <button onClick={handleRefreshStats} aria-label="Refresh workspace statistics" className="p-2.5 text-slate-500 hover:text-primary transition-colors bg-card border border-slate-300 rounded-md">
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
      <aside className="w-72 border-l border-slate-300 bg-secondary/50 flex flex-col shrink-0">
        <div className="p-6 border-b border-slate-300">
           <h3 className="text-xs font-black uppercase tracking-[0.2em] text-slate-500 mb-4">Largest Assets</h3>
           <div className="space-y-2 max-h-[300px] overflow-y-auto custom-scrollbar pr-2">
              {stats?.top_files.map((file, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSelectFile(file)}
                  className="w-full text-left p-3 bg-secondary/40 border border-slate-200 rounded-xl hover:bg-secondary/60 hover:border-primary/30 transition-all group"
                >
                  <div className="flex justify-between items-start gap-2">
                    <span className="text-[11px] font-bold truncate text-ink-soft group-hover:text-primary flex-1">{file.name}</span>
                    <span className="text-[10px] font-mono text-primary shrink-0">{file.size_str}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-[8px] text-slate-600 uppercase tracking-widest font-black">{file.type}</span>
                    <div className="flex-1 h-0.5 bg-slate-200 rounded-full overflow-hidden">
                       <div className="h-full bg-primary/40" style={{ width: '40%' }} />
                    </div>
                  </div>
                </button>
              ))}
              {!stats && <div className="text-center py-10 text-[10px] text-slate-600 italic px-4 leading-relaxed">Connect a workspace folder to see your largest files here.</div>}
           </div>
        </div>

        {/* Engine Logs */}
        <div className="flex-1 flex flex-col min-h-0">
           <div className="px-6 py-4 border-b border-slate-300 flex justify-between items-center bg-secondary/40">
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Live Console</span>
              <button onClick={() => setLogs([])} className="text-[8px] text-slate-700 hover:text-slate-500 uppercase font-black">Flush</button>
           </div>
           <div className="flex-1 overflow-y-auto p-6 font-mono text-[10px] space-y-2 custom-scrollbar">
              {logs.length === 0 && <div className="text-slate-600 italic">Operation activity will appear here.</div>}
              {logs.map((log, i) => (
                <div key={i} className="flex gap-3 leading-relaxed">
                  <span className="text-slate-800 shrink-0 select-none">[{log.timestamp}]</span>
                  <span className={log.type === 'error' ? 'text-red-600' : log.type === 'success' ? 'text-emerald-700' : 'text-slate-600'}>
                    {log.message}
                  </span>
                </div>
              ))}
           </div>
        </div>
      </aside>

      {/* ── Asset Preview Overlay ── */}
      {sidebarOpen && selectedFile && (
        <div className="fixed inset-y-0 right-0 w-[400px] bg-card border-l border-slate-300 shadow-[-4px_0_24px_rgba(31,27,22,0.12)] z-[150] p-10 flex flex-col animate-in slide-in-from-right duration-300">
           <div className="flex justify-between items-center mb-10">
              <h3 className="text-sm font-black uppercase tracking-[0.3em] text-primary">Metadata Insight</h3>
              <button onClick={() => setSidebarOpen(false)} aria-label="Close file details panel" className="w-10 h-10 rounded-full hover:bg-secondary/50 flex items-center justify-center transition-colors">
                <X className="w-6 h-6" />
              </button>
           </div>

           <div className="aspect-square glass-card bg-secondary border-slate-200 flex items-center justify-center mb-10 overflow-hidden shadow-2xl">
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
                 <div className="text-sm text-ink font-bold leading-snug break-all">{selectedFile.name}</div>
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
                 <div className="text-sm text-ink-soft">{selectedFile.modified}</div>
              </div>

              <div className="pt-6 border-t border-slate-200">
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
        <div role="alertdialog" aria-modal="true" aria-labelledby="system-warning-title" className="fixed inset-0 bg-ink/70 backdrop-blur-sm flex items-center justify-center z-[200] p-10">
          <div className="w-[500px] bg-card border border-accent/40 rounded-2xl p-12 shadow-[3px_5px_0_rgba(31,27,22,0.14)] flex flex-col gap-8 text-center">
            <div className="mx-auto w-20 h-20 rounded-full bg-accent/10 border border-accent/30 flex items-center justify-center">
              <ShieldAlert className="w-10 h-10 text-accent" aria-hidden="true" />
            </div>
            <div>
               <h2 id="system-warning-title" className="text-2xl font-black text-ink mb-4 font-serif">Critical Protection Shield</h2>
               <p className="text-ink-soft text-sm leading-relaxed">
                 You have selected a <span className="text-accent font-bold underline">Root or System partition</span>. 
                 Proceeding here can lead to unrecoverable system failure. Do you have explicit clearance?
               </p>
            </div>
            <div className="bg-accent/5 border border-accent/20 rounded-lg p-4 font-mono text-xs text-accent break-all">
              {pendingSystemPath}
            </div>
            <div className="flex gap-4">
              <button autoFocus onClick={() => { setShowSystemWarning(false); setPendingSystemPath(''); }} aria-label="Abort — do not proceed with this system directory" className="flex-1 py-4 bg-secondary border border-slate-300 text-ink rounded-md text-xs font-black uppercase tracking-widest hover:bg-slate-200 transition-all">Abort</button>
              <button onClick={handleConfirmSystemPath} aria-label="Manual override — proceed anyway" className="flex-1 py-4 bg-accent text-on-accent rounded-md text-xs font-black uppercase tracking-widest hover:bg-accent/90 transition-all" style={{ boxShadow: '1px 2px 0 rgba(31,27,22,0.2)' }}>Manual Override</button>
            </div>
          </div>
        </div>
      )}

      {previewItems && (
        <div role="dialog" aria-modal="true" aria-labelledby="preview-dialog-title" className="fixed inset-0 bg-ink/70 backdrop-blur-sm flex items-center justify-center z-[190] p-10">
          <div className="w-[640px] max-h-[80vh] bg-card border border-slate-300 rounded-2xl p-8 shadow-[3px_5px_0_rgba(31,27,22,0.1)] flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 id="preview-dialog-title" className="text-lg font-black text-ink flex items-center gap-2 font-serif">
                <FileSearch className="w-5 h-5 text-primary" aria-hidden="true" />
                Simulation Preview — {previewItems.opTitle}
              </h2>
              <button onClick={() => setPreviewItems(null)} aria-label="Close preview" className="w-9 h-9 rounded-full hover:bg-secondary/70 flex items-center justify-center text-ink-soft">✕</button>
            </div>
            <p className="text-xs text-ink-soft">
              {previewItems.items.length} planned change{previewItems.items.length !== 1 ? 's' : ''} — nothing has been moved yet. Turn off Dry Run and re-run to apply.
            </p>
            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-2">
              {previewItems.items.map((item, i) => (
                <div key={i} className="bg-secondary/40 border border-slate-200 rounded-lg p-3 text-xs font-mono flex flex-col gap-1">
                  <span className="text-ink-soft truncate">{item.src}</span>
                  <span className="text-filed truncate">→ {item.dst}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {confirmDialog && (
        <div role="alertdialog" aria-modal="true" aria-labelledby="confirm-dialog-title" className="fixed inset-0 bg-ink/70 backdrop-blur-sm flex items-center justify-center z-[200] p-10">
          <div className="w-[480px] bg-card border border-amber-500/40 rounded-2xl p-10 shadow-[3px_5px_0_rgba(31,27,22,0.14)] flex flex-col gap-6 text-center">
            <div className="mx-auto w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
              <ShieldAlert className="w-8 h-8 text-amber-600" aria-hidden="true" />
            </div>
            <div>
              <h2 id="confirm-dialog-title" className="text-xl font-black text-ink mb-3 font-serif">{confirmDialog.title}</h2>
              <p className="text-ink-soft text-sm leading-relaxed">{confirmDialog.message}</p>
            </div>
            <div className="flex gap-4">
              <button autoFocus onClick={() => setConfirmDialog(null)} aria-label="Cancel this operation" className="flex-1 py-3 bg-secondary border border-slate-300 text-ink rounded-md text-xs font-black uppercase tracking-widest hover:bg-slate-200 transition-all">Cancel</button>
              <button onClick={confirmDialog.onConfirm} aria-label="Confirm and proceed" className="flex-1 py-3 bg-amber-600 text-on-amber rounded-md text-xs font-black uppercase tracking-widest hover:bg-amber-500 transition-all" style={{ boxShadow: '1px 2px 0 rgba(31,27,22,0.2)' }}>Proceed</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Privacy Policy & Terms Modal (First-Run & On-Demand) ── */}
      {showTermsModal && (
        <div role="dialog" aria-modal="true" aria-labelledby="terms-dialog-title" className="fixed inset-0 bg-ink/75 backdrop-blur-sm flex items-center justify-center z-[250] p-4 md:p-8">
          <div className="w-full max-w-2xl max-h-[85vh] bg-card border border-slate-300 rounded-2xl p-6 md:p-8 shadow-[3px_5px_0_rgba(31,27,22,0.15)] flex flex-col gap-5">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/30 flex items-center justify-center shrink-0">
                  <ShieldCheck className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <h2 id="terms-dialog-title" className="text-lg font-black text-ink font-serif leading-tight">
                    Privacy Guarantee & Terms of Use
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Folders Organizer Pro is 100% local, offline, and open-source.
                  </p>
                </div>
              </div>
              {hasAcceptedTerms && (
                <button
                  onClick={() => setShowTermsModal(false)}
                  aria-label="Close"
                  className="w-8 h-8 rounded-full hover:bg-secondary flex items-center justify-center text-slate-500 hover:text-ink transition-colors"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Tab Selector */}
            <div className="flex gap-2 p-1 bg-secondary/70 border border-slate-300 rounded-lg shrink-0">
              <button
                onClick={() => setTermsTab('privacy')}
                className={`flex-1 py-2 px-3 rounded-md text-xs font-bold transition-all flex items-center justify-center gap-2 ${
                  termsTab === 'privacy'
                    ? 'bg-card text-primary shadow-[1px_1px_0_rgba(31,27,22,0.1)] border border-slate-300'
                    : 'text-slate-600 hover:text-ink'
                }`}
              >
                <ShieldCheck className="w-4 h-4" />
                <span>Privacy Policy (100% Local)</span>
              </button>
              <button
                onClick={() => setTermsTab('terms')}
                className={`flex-1 py-2 px-3 rounded-md text-xs font-bold transition-all flex items-center justify-center gap-2 ${
                  termsTab === 'terms'
                    ? 'bg-card text-primary shadow-[1px_1px_0_rgba(31,27,22,0.1)] border border-slate-300'
                    : 'text-slate-600 hover:text-ink'
                }`}
              >
                <FileText className="w-4 h-4" />
                <span>Terms of Use & Disclaimer</span>
              </button>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-3 text-xs leading-relaxed text-ink-soft">
              {termsTab === 'privacy' ? (
                <>
                  <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl space-y-1">
                    <div className="font-bold text-emerald-700 flex items-center gap-2">
                      <span className="text-sm">🛡️</span> Zero Data Collection & 100% Local
                    </div>
                    <p className="text-slate-600 text-[11px]">
                      Folders Organizer Pro does not collect, track, or transmit any personal data, file contents, or device information.
                    </p>
                  </div>

                  <div className="p-3.5 bg-secondary/40 border border-slate-200 rounded-xl space-y-1">
                    <div className="font-bold text-ink flex items-center gap-2">
                      <span className="text-sm">🚫</span> No Telemetry, Analytics, or Network Calls
                    </div>
                    <p className="text-slate-600 text-[11px]">
                      The application functions entirely offline without external API connections, telemetry daemons, tracking pixels, or advertisements.
                    </p>
                  </div>

                  <div className="p-3.5 bg-secondary/40 border border-slate-200 rounded-xl space-y-1">
                    <div className="font-bold text-ink flex items-center gap-2">
                      <span className="text-sm">📂</span> Strict Local Filesystem Access
                    </div>
                    <p className="text-slate-600 text-[11px]">
                      File scanning, hashing, renaming, and conversions happen solely within the directories you explicitly open. Nothing leaves your PC.
                    </p>
                  </div>

                  <div className="p-3.5 bg-secondary/40 border border-slate-200 rounded-xl space-y-1">
                    <div className="font-bold text-ink flex items-center gap-2">
                      <span className="text-sm">💾</span> Local Undo Snapshots
                    </div>
                    <p className="text-slate-600 text-[11px]">
                      The <code className="bg-secondary px-1 py-0.5 rounded border border-slate-300">.organizer_history.json</code> file is stored strictly in your organized workspace folder for rollback purposes.
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <div className="p-3.5 bg-primary/10 border border-primary/20 rounded-xl space-y-1">
                    <div className="font-bold text-primary flex items-center gap-2">
                      <span className="text-sm">⚖️</span> GPLv3 Open Source License
                    </div>
                    <p className="text-slate-600 text-[11px]">
                      Folders Organizer Pro is free and open-source software under the GNU General Public License v3.
                    </p>
                  </div>

                  <div className="p-3.5 bg-secondary/40 border border-slate-200 rounded-xl space-y-1">
                    <div className="font-bold text-ink flex items-center gap-2">
                      <span className="text-sm">🛡️</span> User Responsibility & Backups
                    </div>
                    <p className="text-slate-600 text-[11px]">
                      You are responsible for your data. We strongly recommend maintaining regular backups and testing batch tasks with <strong>Simulation Mode (Dry Run)</strong> first.
                    </p>
                  </div>

                  <div className="p-3.5 bg-secondary/40 border border-slate-200 rounded-xl space-y-1">
                    <div className="font-bold text-ink flex items-center gap-2">
                      <span className="text-sm">🔒</span> Built-in Safety Nets
                    </div>
                    <p className="text-slate-600 text-[11px]">
                      Includes system-critical folder guards (<code className="bg-secondary px-1 py-0.5 rounded border border-slate-300">C:\Windows</code>, Program Files), Recycle Bin deletion (<code className="bg-secondary px-1 py-0.5 rounded border border-slate-300">send2trash</code>), and atomic undo history.
                    </p>
                  </div>

                  <div className="p-3.5 bg-amber-500/10 border border-amber-500/20 rounded-xl space-y-1">
                    <div className="font-bold text-amber-700 flex items-center gap-2">
                      <span className="text-sm">⚠️</span> Disclaimer of Warranty (AS-IS)
                    </div>
                    <p className="text-slate-600 text-[11px]">
                      Provided "AS IS", without warranty of any kind. Authors are not liable for accidental data loss resulting from filesystem operations.
                    </p>
                  </div>
                </>
              )}
            </div>

            {/* Footer Action */}
            <div className="pt-3 border-t border-slate-200 flex flex-col gap-2">
              {!hasAcceptedTerms ? (
                <>
                  <button
                    onClick={handleAcceptTerms}
                    className="w-full py-3.5 bg-primary text-white rounded-md text-xs font-black uppercase tracking-widest hover:bg-primary/90 transition-all shadow-[1px_2px_0_rgba(31,27,22,0.2)] active:scale-[0.99]"
                  >
                    Accept & Continue
                  </button>
                  <p className="text-[10px] text-center text-slate-500">
                    By clicking Accept & Continue, you acknowledge and agree to these local terms.
                  </p>
                </>
              ) : (
                <button
                  onClick={() => setShowTermsModal(false)}
                  className="w-full py-2.5 bg-secondary text-ink border border-slate-300 rounded-md text-xs font-bold uppercase tracking-wider hover:bg-slate-200 transition-all"
                >
                  Close
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {loading && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex flex-col items-center justify-center z-[300]">
          <div className="relative w-48 h-48">
            <svg className="w-full h-full transform -rotate-90">
              <circle cx="96" cy="96" r="88" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-slate-700" />
              <circle cx="96" cy="96" r="88" stroke="currentColor" strokeWidth="8" fill="transparent" strokeDasharray={552.92} strokeDashoffset={552.92 - (552.92 * progress) / 100} className="text-primary transition-all duration-300 ease-out" />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-4xl font-black text-white">{progress}%</span>
              <span className="text-[10px] font-black text-primary uppercase tracking-[0.2em] mt-1">Complete</span>
            </div>
          </div>
          <p className="mt-10 text-[10px] font-black text-slate-500 tracking-[0.5em] uppercase animate-pulse">Processing Records</p>
        </div>
      )}
    </div>
  );
};

export default App;
