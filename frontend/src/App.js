import React, { useState, useCallback, useRef } from 'react';
import './App.css';
import {
  Camera,
  Video,
  Activity,
  FileText,
  Play,
  Upload,
  X,
  CheckCircle,
  AlertCircle,
  Info,
  Moon,
  Sun,
  Download,
  RotateCcw,
  Menu,
  RefreshCw
} from 'lucide-react';

// ==================== API CONFIGURATION ====================
const API_BASE_URL = 'https://wurdboss-avlprdl-backend.hf.space';
const LIVE_POLL_INTERVAL = 2000;
const CAMERA_TIMEOUT_MS = 8000;

// ==================== VOTING CONFIGURATION ====================
const VOTE_THRESHOLD = 2;       // Need this many matching reads to confirm
const VOTE_WINDOW_MS = 15000;   // INCREASED: Gives the cloud server enough time to process 2 frames

// ==================== LOCAL READ PLATE LOGGING ====================
const READ_PLATE_LOGS_KEY = 'avlprdl_read_plate_logs';
const MAX_LOCAL_LOGS = 500;

const isReadablePlate = (result) => {
  const plate = String(result?.plate_number || '').trim();
  return (
    plate &&
    plate !== 'Not Found' &&
    plate !== 'Error' &&
    plate.toLowerCase() !== 'unknown'
  );
};

const getResultState = (result) => {
  return (
    result?.state_of_origin ||
    result?.detected_state ||
    result?.state ||
    'Unknown'
  );
};

const parseConfidence = (value) => {
  if (value === null || value === undefined || value === '') return null;
  const clean = String(value).replace('%', '').trim();
  const num = Number(clean);
  return Number.isFinite(num) ? num : null;
};

const formatConfidence = (value) => {
  const num = parseConfidence(value);
  if (num === null) return '--';
  return `${Number.isInteger(num) ? num : num.toFixed(1)}%`;
};

const loadPlateLogs = () => {
  try {
    const raw = localStorage.getItem(READ_PLATE_LOGS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const savePlateLogs = (logs) => {
  try {
    localStorage.setItem(READ_PLATE_LOGS_KEY, JSON.stringify(logs));
  } catch {
    // ignore
  }
};

const buildDashboardFromLogs = (logs) => {
  const states = {};
  let confidenceSum = 0;
  let confidenceCount = 0;

  logs.forEach((item) => {
    const state = item.state_of_origin || item.state || 'Unknown';
    if (state && state !== 'Unknown') {
      states[state] = (states[state] || 0) + 1;
    }
    const conf = parseConfidence(item.confidence);
    if (conf !== null) {
      confidenceSum += conf;
      confidenceCount += 1;
    }
  });

  const avgConfidence =
    confidenceCount > 0
      ? Number((confidenceSum / confidenceCount).toFixed(1))
      : 0;

  return {
    total: logs.length,
    states,
    avg_confidence: avgConfidence,
    recent: logs.slice(0, 10)
  };
};

const createLogEntry = (result) => {
  if (!isReadablePlate(result)) return null;
  return {
    id: result.id || `${Date.now()}-${Math.random()}`,
    filename: result.filename || 'Unknown file',
    plate_number: result.plate_number,
    state_of_origin: getResultState(result),
    confidence: parseConfidence(result.confidence) ?? 0,
    status: 'processed',
    message: result.message || 'License plate detected successfully',
    source: result.source || 'upload',
    timestamp: result.timestamp || new Date().toISOString()
  };
};

// ==================== HELPER: getUserMedia with timeout ====================
const getUserMediaWithTimeout = (constraints, timeoutMs = CAMERA_TIMEOUT_MS) => {
  return Promise.race([
    navigator.mediaDevices.getUserMedia(constraints),
    new Promise((_, reject) =>
      setTimeout(() => {
        const err = new Error('Camera request timed out');
        err.name = 'TimeoutError';
        reject(err);
      }, timeoutMs)
    )
  ]);
};

// ==================== HELPER: Friendly camera label ====================
const getCameraDisplayLabel = (cam, index) => {
  if (cam.label && cam.label.trim()) {
    return cam.label.replace(/\s*\([0-9a-f]{4}:[0-9a-f]{4}\)\s*$/i, '');
  }
  return `Camera ${index + 1}`;
};

function App() {
  // ==================== STATE MANAGEMENT ====================
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploadType, setUploadType] = useState('image');
  const [files, setFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');
  const [showUploadPanel, setShowUploadPanel] = useState(false);
  const [showErrorModal, setShowErrorModal] = useState(false);
  const [showAboutModal, setShowAboutModal] = useState(false);
  const [showLiveModal, setShowLiveModal] = useState(false);
  const [liveData, setLiveData] = useState({
    recent: [],
    live_detections: [],
    total: 0,
    timestamp: null
  });
  const [connectionStatus, setConnectionStatus] = useState('checking');
  const [toast, setToast] = useState(null);
  const [darkMode, setDarkMode] = useState(true);

  const [sidebarOpen, setSidebarOpen] = useState(() => {
    return window.innerWidth >= 1024;
  });

  const [activeSection, setActiveSection] = useState('home');
  const [processingCount, setProcessingCount] = useState(0);
  const [processingStatus, setProcessingStatus] = useState(null);

  // ==================== LIVE CAMERA STATE ====================
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [cameraStream, setCameraStream] = useState(null);
  const [cameraError, setCameraError] = useState('');
  const [liveDetections, setLiveDetections] = useState([]);
  const [isProcessingFrame, setIsProcessingFrame] = useState(false);
  const [cameraStatus, setCameraStatus] = useState('idle');
  const [availableCameras, setAvailableCameras] = useState([]);
  const [selectedCameraId, setSelectedCameraId] = useState('');
  const [activeCameraLabel, setActiveCameraLabel] = useState('');

  // ==================== VOTING STATE ====================
  const [voteProgress, setVoteProgress] = useState({});

  // ==================== REFS ====================
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const captureIntervalRef = useRef(null);
  const cameraStreamRef = useRef(null);
  const livePollingRef = useRef(null);
  const processingFrameRef = useRef(false);
  const livePlateSetRef = useRef(new Set());
  const plateVotesRef = useRef(new Map()); // For multi-frame consensus
  
  // Ref for local video processing canvas
  const localVideoCanvasRef = useRef(document.createElement('canvas'));

  // ==================== TOAST NOTIFICATION ====================
  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  }, []);

  // ==================== LOG READ PLATES ====================
  const logReadPlates = useCallback((items) => {
    const entries = (items || []).map(createLogEntry).filter(Boolean);
    if (entries.length === 0) return [];

    const existing = loadPlateLogs();
    const makeKey = (item) =>
      `${item.plate_number}|${item.filename}|${item.source || ''}`;
    const existingKeys = new Set(existing.map(makeKey));

    const freshEntries = entries.filter((entry) => {
      const key = makeKey(entry);
      if (existingKeys.has(key)) return false;
      existingKeys.add(key);
      return true;
    });

    if (freshEntries.length === 0) return [];

    const merged = [...freshEntries, ...existing].slice(0, MAX_LOCAL_LOGS);
    savePlateLogs(merged);
    setDashboardData(buildDashboardFromLogs(merged));
    return freshEntries;
  }, []);

  // ==================== CAMERA: ENUMERATE DEVICES ====================
  const enumerateCameras = async () => {
    try {
      if (!navigator.mediaDevices?.enumerateDevices) return [];

      try {
        const tempStream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false
        });
        tempStream.getTracks().forEach((t) => {
          try { t.stop(); } catch { /* ignore */ }
        });
      } catch (_) {
        // Permission denied — labels stay hidden but devices listed
      }

      const devices = await navigator.mediaDevices.enumerateDevices();
      const cams = devices.filter((d) => d.kind === 'videoinput');
      console.log(
        `[Camera] Found ${cams.length} camera(s):`,
        cams.map((c) => c.label || 'Unlabeled')
      );
      setAvailableCameras(cams);
      return cams;
    } catch (err) {
      console.warn('[Camera] enumerateDevices failed:', err);
      return [];
    }
  };

  // ==================== CAMERA: START ====================
  const startCamera = async () => {
    setCameraStatus('starting');
    setCameraError('');

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraStatus('error');
      setCameraError(
        'Camera API not available. Use Chrome / Edge / Firefox over http://localhost or https.'
      );
      showToast('Browser not supported', 'error');
      return;
    }

    const cams = await enumerateCameras();
    if (cams.length === 0) {
      setCameraStatus('error');
      setCameraError(
        'No camera detected. Connect a USB webcam or built-in camera and try again.'
      );
      showToast('No camera found', 'error');
      return;
    }

    const baseVideoConstraints = selectedCameraId
      ? { deviceId: { exact: selectedCameraId } }
      : { facingMode: { ideal: 'environment' } };

    const constraintsToTry = [
      {
        video: {
          ...baseVideoConstraints,
          width:  { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      },
      {
        video: {
          ...baseVideoConstraints,
          width:  { ideal: 640 },
          height: { ideal: 480 }
        },
        audio: false
      },
      {
        video: selectedCameraId
          ? { deviceId: { exact: selectedCameraId } }
          : true,
        audio: false
      }
    ];

    let stream = null;
    let lastError = null;

    for (let i = 0; i < constraintsToTry.length; i++) {
      try {
        console.log(`[Camera] Attempt ${i + 1}/${constraintsToTry.length}...`);
        stream = await getUserMediaWithTimeout(
          constraintsToTry[i],
          CAMERA_TIMEOUT_MS
        );
        if (stream) {
          console.log(`[Camera] Acquired on attempt ${i + 1}`);
          break;
        }
      } catch (err) {
        lastError = err;
        console.warn(`[Camera] Attempt ${i + 1} failed:`, err.name, err.message);
        await new Promise((r) => setTimeout(r, 400));
      }
    }

    if (!stream) {
      setCameraStatus('error');
      cameraStreamRef.current = null;

      let msg = 'Failed to access camera.';
      if (lastError) {
        const name = lastError.name;
        const m = lastError.message || '';
        if (name === 'NotAllowedError' || name === 'SecurityError') {
          msg = 'Camera permission denied. Click the 🔒 icon in address bar and allow camera access.';
        } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
          msg = 'No camera found. If using USB webcam, ensure it is plugged in.';
        } else if (
          name === 'NotReadableError' ||
          name === 'TrackStartError' ||
          name === 'TimeoutError' ||
          /timeout/i.test(m)
        ) {
          msg = 'Camera is busy. Close other apps using camera (Zoom/Teams/Skype/OBS) and retry.';
        } else if (name === 'OverconstrainedError') {
          msg = 'Camera does not support requested resolution. Try a different camera.';
        } else if (name === 'AbortError') {
          msg = 'Camera start was aborted. Try again.';
        } else {
          msg = `Camera error: ${m || name}`;
        }
      }

      setCameraError(msg);
      showToast(msg, 'error');
      return;
    }

    const track = stream.getVideoTracks()[0];
    const actualLabel = track ? track.label : '';
    console.log('[Camera] Active:', actualLabel, track?.getSettings());
    setActiveCameraLabel(actualLabel || 'Unknown camera');

    cameraStreamRef.current = stream;
    setCameraStream(stream);
    setIsMonitoring(true);
    setCameraStatus('active');

    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      try {
        await videoRef.current.play();
        console.log('[Camera] Video playback started');
      } catch (playErr) {
        console.warn('[Camera] play() error:', playErr);
      }
    }

    // Clear any old votes when starting a new session
    plateVotesRef.current.clear();
    setVoteProgress({});

    startFrameCapture();
    showToast(`Camera started: ${actualLabel ? actualLabel.slice(0, 30) : 'OK'}`, 'success');
  };

  // ==================== CAMERA: STOP ====================
  const stopCamera = () => {
    setCameraStatus('stopping');

    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current);
      captureIntervalRef.current = null;
    }

    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach((track) => {
        try { track.stop(); } catch { /* ignore */ }
      });
      cameraStreamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setCameraStream(null);
    setIsMonitoring(false);
    setCameraStatus('idle');
    setActiveCameraLabel('');
    plateVotesRef.current.clear();
    setVoteProgress({});
    showToast('Camera stopped', 'info');
  };

  // ==================== CAMERA: RETRY ====================
  const retryCamera = async () => {
    setCameraError('');
    setCameraStatus('idle');
    await new Promise((r) => setTimeout(r, 300));
    await startCamera();
  };

  // ==================== CAMERA: SWITCH ====================
  const switchCamera = async (newDeviceId) => {
    setSelectedCameraId(newDeviceId);
    if (cameraStatus === 'active') {
      stopCamera();
      await new Promise((r) => setTimeout(r, 500));
      setTimeout(() => startCamera(), 100);
    }
  };

  // ==================== FRAME CAPTURE & SEND WITH VOTING ====================
  const captureAndSendFrame = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    if (processingFrameRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    if (video.readyState !== 4) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    if (!canvas.width || !canvas.height) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', 0.95)  // higher quality
    );
    if (!blob) return;

    processingFrameRef.current = true;
    setIsProcessingFrame(true);

    try {
      const formData = new FormData();
      formData.append('frame', blob, 'frame.jpg');

      const response = await fetch(`${API_BASE_URL}/api/image`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        setConnectionStatus('connected');
        const data = await response.json();
        console.log('[LIVE FRAME RESPONSE]', data);

        if (isReadablePlate(data)) {
          const plate = data.plate_number;
          const now = Date.now();
          const votes = plateVotesRef.current;

          // Clean up expired votes
          for (const [key, info] of votes.entries()) {
            if (now - info.lastSeen > VOTE_WINDOW_MS) {
              votes.delete(key);
            }
          }

          // Normalize plate key for voting
          const normalizedKey = plate.replace(/[^A-Z0-9]/g, '');

          const existing = votes.get(normalizedKey) || {
            count: 0,
            bestConfidence: 0,
            bestPlate: plate,
            bestState: getResultState(data),
            firstSeen: now,
            lastSeen: now,
            confirmed: false,
          };

          existing.count += 1;
          existing.lastSeen = now;

          // Keep highest-confidence variant as canonical
          if ((data.confidence || 0) > existing.bestConfidence) {
            existing.bestConfidence = data.confidence || 0;
            existing.bestPlate = plate;
            existing.bestState = getResultState(data);
          }

          votes.set(normalizedKey, existing);

          // Update vote progress for UI
          setVoteProgress((prev) => {
            const next = { ...prev };
            // Clean expired
            Object.keys(next).forEach((k) => {
              if (!votes.has(k) || votes.get(k).confirmed) {
                delete next[k];
              }
            });
            // Add current
            if (!existing.confirmed) {
              next[normalizedKey] = {
                plate: existing.bestPlate,
                count: existing.count,
                needed: VOTE_THRESHOLD,
              };
            }
            return next;
          });

          // Confirm plate when threshold reached
          if (existing.count >= VOTE_THRESHOLD && !existing.confirmed) {
            existing.confirmed = true;

            const liveResult = {
              filename: 'Live Camera',
              plate_number: existing.bestPlate,
              state_of_origin: existing.bestState,
              confidence: existing.bestConfidence,
              status: 'processed',
              message: `Confirmed after ${existing.count} reads`,
              source: 'live-camera',
              timestamp: new Date().toISOString(),
            };

            logReadPlates([liveResult]);

            // Push to backend
            try {
              await fetch(`${API_BASE_URL}/api/live-data/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(liveResult),
              });
            } catch { /* non-blocking */ }

            if (!livePlateSetRef.current.has(existing.bestPlate)) {
              livePlateSetRef.current.add(existing.bestPlate);
              setLiveDetections((prev) => [
                {
                  plate_number: existing.bestPlate,
                  state: existing.bestState,
                  confidence: existing.bestConfidence,
                  timestamp: new Date().toISOString(),
                  id: Date.now() + Math.random(),
                },
                ...prev,
              ].slice(0, 50));
              showToast(`✅ Confirmed: ${existing.bestPlate}`, 'success');
            }

            // Remove from vote progress UI
            setVoteProgress((prev) => {
              const next = { ...prev };
              delete next[normalizedKey];
              return next;
            });
          } else {
            console.log(`[VOTE] ${normalizedKey}: ${existing.count}/${VOTE_THRESHOLD}`);
          }
        }
      } else {
        setConnectionStatus('disconnected');
      }
    } catch (err) {
      console.error('Frame processing error:', err);
      setConnectionStatus('disconnected');
    } finally {
      processingFrameRef.current = false;
      setIsProcessingFrame(false);
    }
  };

  const startFrameCapture = () => {
    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current);
    }
    // Slower interval gives camera time to auto-focus
    captureIntervalRef.current = setInterval(captureAndSendFrame, 2500);
  };

  const toggleMonitoring = () => {
    if (isMonitoring) {
      stopCamera();
    } else {
      startCamera();
    }
  };

  // ==================== EFFECTS ====================
  React.useEffect(() => {
    if (
      cameraStatus === 'active' &&
      videoRef.current &&
      cameraStreamRef.current
    ) {
      if (!videoRef.current.srcObject) {
        videoRef.current.srcObject = cameraStreamRef.current;
        videoRef.current.play().catch(() => {});
      }
    }
  }, [cameraStatus]);

  React.useEffect(() => {
    if (!navigator.mediaDevices?.addEventListener) return;
    const handleDeviceChange = () => {
      console.log('[Camera] Devices changed — re-enumerating');
      if (showLiveModal) enumerateCameras();
    };
    navigator.mediaDevices.addEventListener('devicechange', handleDeviceChange);
    return () => {
      navigator.mediaDevices.removeEventListener('devicechange', handleDeviceChange);
    };
  }, [showLiveModal]);

  React.useEffect(() => {
    if (!showLiveModal) {
      if (captureIntervalRef.current) {
        clearInterval(captureIntervalRef.current);
        captureIntervalRef.current = null;
      }
      if (cameraStreamRef.current) {
        cameraStreamRef.current.getTracks().forEach((track) => {
          try { track.stop(); } catch { /* ignore */ }
        });
        cameraStreamRef.current = null;
      }
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
      processingFrameRef.current = false;
      livePlateSetRef.current.clear();
      plateVotesRef.current.clear();
      setVoteProgress({});
      setCameraStream(null);
      setIsMonitoring(false);
      setCameraStatus('idle');
      setLiveDetections([]);
      setCameraError('');
      setActiveCameraLabel('');
    }
  }, [showLiveModal]);

  // ==================== CONNECTION TEST ====================
  const testConnection = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/test`);
      setConnectionStatus(response.ok ? 'connected' : 'disconnected');
    } catch (err) {
      console.error('Connection test failed:', err);
      setConnectionStatus('disconnected');
    }
  };

  // ==================== FETCH DASHBOARD DATA ====================
  const fetchDashboardData = async () => {
    const localLogs = loadPlateLogs();
    const localDashboard = buildDashboardFromLogs(localLogs);
    setDashboardData(localDashboard);

    try {
      const response = await fetch(`${API_BASE_URL}/api/dashboard`);
      if (response.ok) {
        const data = await response.json();
        if (data && Number(data.total || 0) > 0) {
          setDashboardData(data);
        } else {
          setDashboardData(localDashboard);
        }
      }
    } catch (err) {
      console.error('Dashboard fetch error:', err);
      setDashboardData(localDashboard);
    }
  };

  // ==================== FETCH LIVE DATA ====================
  const fetchLiveData = async () => {
    try {
      const localLogs = loadPlateLogs();
      const localDashboard = buildDashboardFromLogs(localLogs);
      const response = await fetch(`${API_BASE_URL}/api/live-data`);
      if (response.ok) {
        const data = await response.json();
        if (data && Number(data.total || 0) > 0) {
          setLiveData(data);
        } else {
          setLiveData({
            recent: localDashboard.recent,
            live_detections: localDashboard.recent,
            total: localDashboard.total,
            timestamp: new Date().toISOString()
          });
        }
        setConnectionStatus('connected');
      } else {
        setLiveData({
          recent: localDashboard.recent,
          live_detections: localDashboard.recent,
          total: localDashboard.total,
          timestamp: new Date().toISOString()
        });
        setConnectionStatus('disconnected');
      }
    } catch (err) {
      console.error('Live data fetch error:', err);
      const localLogs = loadPlateLogs();
      const localDashboard = buildDashboardFromLogs(localLogs);
      setLiveData({
        recent: localDashboard.recent,
        live_detections: localDashboard.recent,
        total: localDashboard.total,
        timestamp: new Date().toISOString()
      });
      setConnectionStatus('disconnected');
    }
  };

  React.useEffect(() => {
    if (showLiveModal) {
      fetchLiveData();
      livePollingRef.current = setInterval(fetchLiveData, LIVE_POLL_INTERVAL);
    } else {
      if (livePollingRef.current) {
        clearInterval(livePollingRef.current);
        livePollingRef.current = null;
      }
    }
    return () => {
      if (livePollingRef.current) clearInterval(livePollingRef.current);
    };
  }, [showLiveModal]);

  React.useEffect(() => {
    fetchDashboardData();
    testConnection();
  }, []);

  React.useEffect(() => {
    if (darkMode) {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }, [darkMode]);

  // ==================== HANDLERS ====================
  const handleReset = () => {
    setResults([]);
    setDashboardData(buildDashboardFromLogs(loadPlateLogs()));
    setFiles([]);
    setUploadProgress(0);
    setError('');
    setShowUploadPanel(false);
    setShowErrorModal(false);
    setActiveSection('home');
    showToast('Dashboard reset successfully', 'success');
  };

  const handleExportAnalytics = async () => {
    try {
      setLoading(true);
      let exportedResults = [];
      try {
        const response = await fetch(`${API_BASE_URL}/api/export-analytics`);
        if (response.ok) {
          const data = await response.json();
          if (data.data && data.data.length > 0) {
            exportedResults = data.data.map((item, idx) => ({
              filename: item.Image_Name || item.image_name || `Record ${idx + 1}`,
              status: 'processed',
              plate_number: item.Plate_Number || item.plate_number,
              state_of_origin: item.State_of_Origin || item.state_of_origin || 'Unknown',
              confidence: item.Confidence || item.confidence || 0,
              message: 'License plate detected successfully',
              source: 'backend-export'
            }));
          }
        }
      } catch { /* fallback below */ }

      if (exportedResults.length === 0) {
        const localLogs = loadPlateLogs();
        exportedResults = localLogs.map((item) => ({
          filename: item.filename,
          status: 'processed',
          plate_number: item.plate_number,
          state_of_origin: item.state_of_origin || 'Unknown',
          confidence: item.confidence || 0,
          message: 'License plate detected successfully',
          source: 'local-log'
        }));
      }

      if (exportedResults.length > 0) {
        setResults(exportedResults);
        showToast(`Loaded ${exportedResults.length} logged plate(s)`, 'success');
      } else {
        showToast('No logged plates available', 'info');
      }
    } catch (err) {
      console.error('Export analytics error:', err);
      showToast('Network error. Check if backend is running.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleClearLogs = async () => {
    try {
      setLoading(true);
      savePlateLogs([]);
      setResults([]);
      setDashboardData({ total: 0, states: {}, avg_confidence: 0, recent: [] });
      setFiles([]);
      setUploadProgress(0);
      setLiveDetections([]);
      setLiveData({ recent: [], live_detections: [], total: 0, timestamp: null });

      try {
        await fetch(`${API_BASE_URL}/api/clear-logs`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
      } catch { /* ignore */ }

      showToast('All logs cleared successfully', 'success');
    } catch (err) {
      console.error('Clear logs error:', err);
      showToast('Network error while clearing logs', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      setError('Please select file(s) to upload');
      setShowErrorModal(true);
      return;
    }
    setLoading(true);
    setUploadProgress(0);
    setError('');
    setResults([]);
    setProcessingCount(files.length);

    try {
      setUploadProgress(5);
      setProcessingStatus('Preparing upload...');

      // =========================================================================
      // IMAGE UPLOAD LOGIC
      // =========================================================================
      if (uploadType === 'image') {
        const allResults = [];
        let successCount = 0;

        for (let i = 0; i < files.length; i++) {
          const file = files[i];
          setProcessingStatus(`Processing ${file.name} (${i + 1}/${files.length})...`);
          setUploadProgress(Math.round(((i + 1) / files.length) * 90));

          const formData = new FormData();
          formData.append('file', file);

          try {
            const response = await fetch(`${API_BASE_URL}/api/process-image`, {
              method: 'POST',
              body: formData
            });
            if (response.ok) {
              const data = await response.json();
              console.log('[IMAGE RESPONSE]', data);
              const plateFound = isReadablePlate(data);
              allResults.push({
                filename: file.name,
                status: plateFound ? 'processed' : 'not_found',
                plate_number: plateFound ? data.plate_number : 'Not Found',
                state_of_origin: getResultState(data),
                confidence: data.confidence || 0,
                message: plateFound
                  ? 'License plate detected successfully'
                  : 'No license plate detected',
                source: 'image-upload',
                timestamp: new Date().toISOString()
              });
              if (plateFound) successCount += 1;
            } else {
              allResults.push({
                filename: file.name,
                status: 'error',
                plate_number: 'Error',
                state_of_origin: 'Unknown',
                confidence: 0,
                message: `Server error ${response.status}`,
                source: 'image-upload'
              });
            }
          } catch (err) {
            console.error('Image upload error:', err);
            allResults.push({
              filename: file.name,
              status: 'error',
              plate_number: 'Error',
              state_of_origin: 'Unknown',
              confidence: 0,
              message: 'Network error',
              source: 'image-upload'
            });
          }
        }

        setUploadProgress(100);
        setProcessingStatus('Complete!');
        setResults(allResults);
        const logged = logReadPlates(allResults);

        if (successCount > 0) {
          showToast(`Read ${successCount} plate(s). Logged ${logged.length} new.`, 'success');
        } else {
          showToast('Processing complete, no plates detected', 'info');
        }
      } 
      // =========================================================================
      // VIDEO UPLOAD LOGIC (CANVAS EXTRACTION METHOD)
      // =========================================================================
      else {
        setProcessingStatus('Initializing video processing...');
        setUploadProgress(10);
        
        const file = files[0];
        const videoElement = document.createElement('video');
        videoElement.src = URL.createObjectURL(file);
        videoElement.muted = true;
        
        await new Promise((resolve) => {
          videoElement.onloadedmetadata = resolve;
        });

        const canvas = localVideoCanvasRef.current;
        const ctx = canvas.getContext('2d');
        canvas.width = videoElement.videoWidth;
        canvas.height = videoElement.videoHeight;

        const duration = videoElement.duration;
        const interval = 1.5; // Snap a frame every 1.5 seconds
        const totalFramesToExtract = Math.floor(duration / interval);
        
        const videoRawResults = [];
        const seenPlates = new Set();
        const uniqueFound = [];

        setProcessingStatus(`Extracting and analyzing frames...`);

        // Loop through the video at set intervals
        for (let currentTime = 0; currentTime < duration; currentTime += interval) {
          videoElement.currentTime = currentTime;
          
          await new Promise((resolve) => {
            videoElement.onseeked = resolve;
          });

          // Draw the current video frame to our invisible canvas
          ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
          
          // Convert canvas frame to a lightweight blob
          const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.90));
          
          // Send the individual frame to the working /api/image endpoint
          const formData = new FormData();
          formData.append('file', blob, `frame-${currentTime}.jpg`);

          try {
            const response = await fetch(`${API_BASE_URL}/api/image`, {
              method: 'POST',
              body: formData
            });

            if (response.ok) {
              const data = await response.json();
              
              if (isReadablePlate(data)) {
                videoRawResults.push(data);
                
                if (!seenPlates.has(data.plate_number)) {
                  seenPlates.add(data.plate_number);
                  uniqueFound.push({
                    filename: file.name,
                    status: 'processed',
                    plate_number: data.plate_number,
                    state_of_origin: getResultState(data),
                    confidence: data.confidence || 0,
                    message: 'License plate detected successfully',
                    source: 'video-upload',
                    timestamp: new Date().toISOString()
                  });
                }
              }
            }
          } catch (err) {
            console.error(`Error analyzing frame at ${currentTime}s`, err);
          }

          // Update progress bar
          const progress = 10 + Math.round((currentTime / duration) * 80);
          setUploadProgress(progress);
        }

        // Clean up memory
        URL.revokeObjectURL(videoElement.src);
        
        // Finalize results
        setUploadProgress(100);
        setProcessingStatus('Video analysis complete!');
        
        // If nothing was found, output a dummy "Not Found" result for the UI
        const finalResults = uniqueFound.length > 0 ? uniqueFound : [{
          filename: file.name,
          status: 'not_found',
          plate_number: 'Not Found',
          state_of_origin: 'Unknown',
          confidence: 0,
          message: 'No license plate detected in video',
          source: 'video-upload',
          timestamp: new Date().toISOString()
        }];

        setResults(finalResults);
        const logged = logReadPlates(uniqueFound);

        if (uniqueFound.length > 0) {
          showToast(`Found ${uniqueFound.length} unique plate(s). Logged ${logged.length} new.`, 'success');
        } else {
          showToast('Video processed, no plates found', 'info');
        }
      }

      fetchDashboardData();
    } catch (err) {
      console.error('Upload error:', err);
      setError('Network error. Check if backend is running.');
      setShowErrorModal(true);
      showToast('Network error', 'error');
    } finally {
      setLoading(false);
      setTimeout(() => setProcessingStatus(null), 1000);
    }
  };

  const handleAction = async (action) => {
    switch (action) {
      case 'image':
        setUploadType('image');
        setShowUploadPanel(true);
        setFiles([]);
        setError('');
        break;
      case 'video':
        setUploadType('video');
        setShowUploadPanel(true);
        setFiles([]);
        setError('');
        break;
      case 'live':
        setShowLiveModal(true);
        enumerateCameras();
        break;
      case 'analysis':
        await fetchDashboardData();
        setActiveSection('analysis');
        break;
      case 'report':
        await fetchDashboardData();
        showToast('Report generated!', 'success');
        break;
      default:
        break;
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const stats = React.useMemo(() => {
    if (dashboardData && dashboardData.total > 0) {
      const stateCount = dashboardData.states ? Object.keys(dashboardData.states).length : 0;
      return {
        total_detections: dashboardData.total || 0,
        today_detections: dashboardData.recent ? dashboardData.recent.length : 0,
        accuracy_rate: dashboardData.avg_confidence || 0,
        states_covered: stateCount || 0,
        hasData: true
      };
    }
    return {
      total_detections: 0,
      today_detections: 0,
      accuracy_rate: null,
      states_covered: 0,
      hasData: false
    };
  }, [dashboardData]);

  const readableResults = results.filter(isReadablePlate);
  const cameraBusyError = cameraError && /busy|unresponsive|NotReadable/i.test(cameraError);
  const pendingVotes = Object.values(voteProgress).filter((v) => v.count < v.needed);

  // ==================== RENDER ====================
  return (
    <div className={`App ${darkMode ? 'dark-mode' : ''}`}>
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.type === 'success' && <CheckCircle size={20} />}
          {toast.type === 'error' && <AlertCircle size={20} />}
          {toast.type === 'info' && <Info size={20} />}
          <span>{toast.message}</span>
          <button className="toast-close" onClick={() => setToast(null)}>
            <X size={16} />
          </button>
        </div>
      )}

      <button
        className={`mobile-menu-btn ${sidebarOpen ? 'hidden' : ''}`}
        onClick={() => setSidebarOpen(true)}
        aria-label="Open menu"
      >
        <Menu size={24} />
      </button>

      <div
        className={`sidebar-overlay ${sidebarOpen ? 'visible' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      <aside className={`sidebar ${sidebarOpen ? 'open' : 'collapsed'}`}>
        <div className="sidebar-header">
          <div className="logo">
            <img
              src={require('./imageCapture.jpeg')}
              alt="AVLPRDL"
              style={{ width: 32, height: 32, borderRadius: 8 }}
            />
            <span>AVLPRDL System</span>
          </div>
        </div>

        <button className="sidebar-expand" onClick={() => setSidebarOpen(true)}>
          <img
            src={require('./imageCapture.jpeg')}
            alt="AVLPRDL"
            style={{ width: 32, height: 32 }}
          />
        </button>

        <nav className="sidebar-nav">
          <button
            className={`nav-item ${activeSection === 'home' ? 'active' : ''}`}
            onClick={() => setActiveSection('home')}
          >
            <Activity size={20} />
            <span>Dashboard</span>
          </button>
          <button className="nav-item" onClick={handleExportAnalytics}>
            <Download size={20} />
            <span>Export Analytics Result</span>
          </button>
          <button className="nav-item" onClick={handleClearLogs}>
            <RotateCcw size={20} />
            <span>Clear Logs</span>
          </button>
          <button className="nav-item" onClick={() => setShowAboutModal(true)}>
            <Info size={20} />
            <span>About</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <button className="theme-toggle" onClick={() => setDarkMode(!darkMode)}>
            {darkMode ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>
      </aside>

      <main className={`main-content ${sidebarOpen ? '' : 'full-width'}`}>
        <header className="top-header">
          <div className="header-left">
            <h1>
              Automated Vehicle License Plate Recognition (AVLPR)
              <br />
              & Data Logging
            </h1>
            <p>Real-Time Detection & Intelligent Data Archiving</p>
          </div>
        </header>

        <section className="stats-section">
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon stat-icon-1"><Camera size={24} /></div>
              <div className="stat-content">
                <span className="stat-value">{stats.today_detections}</span>
                <span className="stat-label">Recent Detections</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon stat-icon-2"><Activity size={24} /></div>
              <div className="stat-content">
                <span className="stat-value">{stats.total_detections}</span>
                <span className="stat-label">Total Plates</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon stat-icon-3"><CheckCircle size={24} /></div>
              <div className="stat-content">
                <span className="stat-value">{stats.hasData ? `${stats.accuracy_rate}%` : '--'}</span>
                <span className="stat-label">Accuracy Rate</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon stat-icon-4"><FileText size={24} /></div>
              <div className="stat-content">
                <span className="stat-value">{stats.states_covered}</span>
                <span className="stat-label">States Covered</span>
              </div>
            </div>
          </div>
        </section>

        <section className="actions-section">
          <h2>Quick Actions</h2>
          <div className="actions-grid">
            <button className="action-card action-image" onClick={() => handleAction('image')}>
              <div className="action-icon"><Camera size={32} /></div>
              <div className="action-info">
                <h3>Process Image</h3>
                <p>Upload and analyze image files</p>
              </div>
              <div className="action-arrow"><Upload size={20} /></div>
            </button>
            <button className="action-card action-video" onClick={() => handleAction('video')}>
              <div className="action-icon"><Video size={32} /></div>
              <div className="action-info">
                <h3>Analyze Video</h3>
                <p>Process video streams</p>
              </div>
              <div className="action-arrow"><Upload size={20} /></div>
            </button>
            <button className="action-card action-live" onClick={() => handleAction('live')}>
              <div className="action-icon"><Play size={32} /></div>
              <div className="action-info">
                <h3>Live Monitoring</h3>
                <p>Real-Time Detection</p>
              </div>
              <div className="action-arrow"><Play size={20} /></div>
            </button>
          </div>
        </section>

        {readableResults.length > 0 && (
          <section className="results-section">
            <h2>Detection Results</h2>
            <div className="results-grid">
              {readableResults.map((result, index) => (
                <div key={index} className="result-card">
                  <div className="result-header">
                    <span className="result-filename">{result.filename}</span>
                    <span className="result-status processed">PROCESSED</span>
                  </div>
                  <div className="result-body">
                    <p className="result-message">
                      {result.message || 'License plate detected successfully'}
                    </p>
                    <div className="plate-details">
                      <div className="plate-number">
                        <span className="label">Plate Number</span>
                        <span className="value">{result.plate_number}</span>
                      </div>
                      <div className="plate-state">
                        <span className="label">State</span>
                        <span className="value badge">{getResultState(result)}</span>
                      </div>
                      <div className="plate-confidence">
                        <span className="label">Confidence</span>
                        <span className="value">{formatConfidence(result.confidence)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {results.length > 0 && readableResults.length === 0 && (
          <section className="unread-plates-section">
            <h3><AlertCircle size={20} /> No Plate Detected</h3>
            <p>No readable license plate was found in the selected file(s).</p>
          </section>
        )}

        <footer className="app-footer">
          <div className="footer-left">
            <img src="/MYLogo.png" alt="wurdboss" width={25} />
            <span>Uwagboi Andrew Chukwuyem </span>
          </div>
          <div className="footer-right">
            <span>myFinalYearProject©2026</span>
          </div>
        </footer>
      </main>

      {/* Upload Modal */}
      {showUploadPanel && (
        <div className="modal-overlay" onClick={() => setShowUploadPanel(false)}>
          <div className="modal upload-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                {uploadType === 'image'
                  ? <><Camera size={24} /> Upload Images</>
                  : <><Video size={24} /> Upload Video</>
                }
              </h2>
              <button className="modal-close" onClick={() => setShowUploadPanel(false)}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleFileUpload} className="upload-form">
              <div className="file-drop-zone">
                <Upload size={48} />
                <p>
                  Drag and drop or click to select{' '}
                  {uploadType === 'image' ? 'multiple images' : 'a video'}
                </p>
                <input
                  type="file"
                  multiple={uploadType === 'image'}
                  accept={uploadType === 'image'
                    ? '.png,.jpg,.jpeg,.gif,.bmp,.webp'
                    : '.mp4,.avi,.mov,.mkv,.webm'}
                  onChange={(e) => {
                    const newFiles = Array.from(e.target.files);
                    setFiles((prev) =>
                      uploadType === 'image'
                        ? [...prev, ...newFiles]
                        : newFiles.slice(0, 1)
                    );
                  }}
                />
              </div>
              {files.length > 0 && (
                <div className="selected-files">
                  <div className="selected-files-header">
                    <span>Selected Files ({files.length})</span>
                    <button type="button" className="clear-all-btn" onClick={() => setFiles([])}>
                      Clear All
                    </button>
                  </div>
                  <div className="files-list">
                    {files.map((file, index) => (
                      <div key={index} className="file-info">
                        <span className="file-name">{file.name}</span>
                        <span className="file-size">{formatFileSize(file.size)}</span>
                        <button
                          type="button"
                          className="remove-file-btn"
                          onClick={() => setFiles((prev) => prev.filter((_, i) => i !== index))}
                        >
                          <X size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {loading && (
                <div className="progress-info">
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
                  </div>
                  <span className="progress-text">
                    {processingStatus || `Processing ${processingCount} of ${files.length} files...`}
                  </span>
                </div>
              )}
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary"
                  onClick={() => { setShowUploadPanel(false); setFiles([]); }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={loading || files.length === 0}>
                  {loading ? 'Processing...' :
                    `Upload ${files.length > 0 ? `${files.length} ` : ''}${uploadType === 'image' ? 'Image(s)' : 'Video'}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Error Modal */}
      {showErrorModal && error && (
        <div className="modal-overlay" onClick={() => setShowErrorModal(false)}>
          <div className="modal error-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2><AlertCircle size={24} /> Error</h2>
              <button className="modal-close" onClick={() => setShowErrorModal(false)}>
                <X size={20} />
              </button>
            </div>
            <p className="error-message">{error}</p>
            <div className="modal-actions">
              <button className="btn btn-secondary"
                onClick={() => { setShowErrorModal(false); setError(''); }}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* About Modal */}
      {showAboutModal && (
        <div className="modal-overlay" onClick={() => setShowAboutModal(false)}>
          <div className="modal about-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2><Info size={24} /> Student's Details</h2>
              <button className="modal-close" onClick={() => setShowAboutModal(false)}>
                <X size={20} />
              </button>
            </div>
            <div className="about-content">
              <div className="about-hero"><h3>AVLPRDL System</h3></div>
              <div className="about-details">
                <div className="about-item">
                  <span className="about-label">Project Topic</span>
                  <span className="about-value">
                    Developing a Solution for Automated Vehicle License Plate Recognition (AVLPR) & Data Logging
                  </span>
                </div>
                <div className="about-item">
                  <span className="about-label">Supervisor</span>
                  <span className="about-value">Dr. Oluwafemi Samuel O. Abe</span>
                </div>
                <div className="about-item">
                  <span className="about-label">Developer</span>
                  <span className="about-value">Uwagboi Andrew Chukwuyem</span>
                </div>
                <div className="about-item">
                  <span className="about-label">Matric Number</span>
                  <span className="about-value">2203030127</span>
                </div>
                <div className="about-item">
                  <span className="about-label">Department</span>
                  <span className="about-value">Computer Science</span>
                </div>
                <div className="about-item">
                  <span className="about-label">Year</span>
                  <span className="about-value">2026</span>
                </div>
              </div>
              <div className="about-tech">
                <h4>Technologies Used</h4>
                <div className="tech-tags">
                  <span className="tech-tag">React</span>
                  <span className="tech-tag">Python</span>
                  <span className="tech-tag">YOLOv8</span>
                  <span className="tech-tag">Flask</span>
                  <span className="tech-tag">OCR</span>
                </div>
              </div>
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={() => setShowAboutModal(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Live Monitoring Modal */}
      {showLiveModal && (
        <div className="modal-overlay" onClick={() => setShowLiveModal(false)}>
          <div className="modal live-modal live-modal-extra-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2><Activity size={24} /> Live Monitoring</h2>
              <div className="live-status-indicator">
                <span className={`live-dot ${connectionStatus === 'connected' ? 'active' : ''}`} />
                <span className={`live-status-text ${connectionStatus === 'connected' ? 'connected' : ''}`}>
                  {connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              <button className="modal-close" onClick={() => setShowLiveModal(false)}>
                <X size={20} />
              </button>
            </div>

            <div className="live-content">
              <canvas ref={canvasRef} style={{ display: 'none' }} />

              <div className="live-camera-section">
                {availableCameras.length > 0 && (
                  <div className="camera-selector"
                       style={{
                         display: 'flex', alignItems: 'center',
                         gap: 10, marginBottom: 12, flexWrap: 'wrap'
                       }}>
                    <label htmlFor="camera-select" style={{ fontWeight: 600, fontSize: 14 }}>
                      📷 Camera:
                    </label>
                    <select
                      id="camera-select"
                      value={selectedCameraId}
                      onChange={(e) => switchCamera(e.target.value)}
                      disabled={cameraStatus === 'starting' || cameraStatus === 'stopping'}
                      style={{
                        padding: '6px 10px', borderRadius: 6,
                        border: '1px solid var(--border-color, #444)',
                        background: 'var(--bg-secondary, #2a2a2a)',
                        color: 'var(--text-primary, #fff)',
                        fontSize: 13, minWidth: 220, cursor: 'pointer'
                      }}
                    >
                      <option value="">Auto-detect (recommended)</option>
                      {availableCameras.map((cam, idx) => (
                        <option key={cam.deviceId} value={cam.deviceId}>
                          {getCameraDisplayLabel(cam, idx)}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={enumerateCameras}
                      style={{ padding: '6px 10px', fontSize: 12 }}
                      title="Refresh camera list"
                    >
                      <RefreshCw size={14} />
                    </button>
                    {activeCameraLabel && cameraStatus === 'active' && (
                      <span style={{
                        fontSize: 12,
                        color: 'var(--text-secondary, #999)',
                        fontStyle: 'italic'
                      }}>
                        Live: {activeCameraLabel.slice(0, 35)}
                        {activeCameraLabel.length > 35 ? '…' : ''}
                      </span>
                    )}
                  </div>
                )}

                <div className="camera-preview-wrapper">
                  {cameraStatus === 'idle' && (
                    <div className="camera-placeholder">
                      <Camera size={48} />
                      <p>Camera Ready</p>
                      <span>
                        {availableCameras.length > 0
                          ? `${availableCameras.length} camera(s) detected`
                          : 'Click Start Monitoring to begin'}
                      </span>
                    </div>
                  )}
                  {cameraStatus === 'starting' && (
                    <div className="camera-loading">
                      <RefreshCw size={32} className="spin" />
                      <p>Starting camera...</p>
                      <span>This can take a few seconds</span>
                    </div>
                  )}
                  {cameraStatus === 'active' && (
                    <video ref={videoRef} className="camera-video" autoPlay playsInline muted />
                  )}
                  {cameraStatus === 'error' && (
                    <div className="camera-placeholder camera-error-state">
                      <AlertCircle size={48} />
                      <p>Camera Error</p>
                      <span>{cameraError}</span>
                      <button className="btn btn-primary" onClick={retryCamera} style={{ marginTop: 12 }}>
                        <RefreshCw size={16} /> Retry
                      </button>
                    </div>
                  )}
                  {cameraStatus === 'stopping' && (
                    <div className="camera-loading">
                      <RefreshCw size={32} className="spin" />
                      <p>Stopping camera...</p>
                    </div>
                  )}
                </div>

                {/* ==================== VOTING PROGRESS INDICATOR ==================== */}
                {pendingVotes.length > 0 && cameraStatus === 'active' && (
                  <div style={{
                    marginTop: 10,
                    padding: '10px 12px',
                    background: 'rgba(100, 150, 255, 0.1)',
                    border: '1px solid rgba(100, 150, 255, 0.3)',
                    borderRadius: 6,
                    fontSize: 13,
                    color: 'var(--text-secondary, #ccc)',
                    lineHeight: 1.5
                  }}>
                    🔍 <strong>Verifying:</strong>{' '}
                    {pendingVotes.map((v, i) => (
                      <span key={i} style={{ marginRight: 12 }}>
                        <strong>{v.plate}</strong> ({v.count}/{v.needed} reads)
                      </span>
                    ))}
                  </div>
                )}

                <div className="camera-controls">
                  <button
                    className={`btn ${isMonitoring ? 'btn-danger' : 'btn-success'} btn-camera-toggle`}
                    onClick={toggleMonitoring}
                    disabled={cameraStatus === 'starting' || cameraStatus === 'stopping'}
                  >
                    {cameraStatus === 'starting' || cameraStatus === 'stopping' ? (
                      <>
                        <RefreshCw size={18} className="spin" />
                        {isMonitoring ? 'Stopping...' : 'Starting...'}
                      </>
                    ) : isMonitoring ? (
                      <><X size={18} /> Stop Monitoring</>
                    ) : (
                      <><Play size={18} /> Start Monitoring</>
                    )}
                  </button>

                  {cameraStatus === 'error' && (
                    <button className="btn btn-secondary" onClick={retryCamera}>
                      <RefreshCw size={16} /> Retry
                    </button>
                  )}

                  {isProcessingFrame && (
                    <div className="camera-processing-indicator">
                      <RefreshCw size={16} className="spin" />
                      <span>Processing...</span>
                    </div>
                  )}
                </div>

                {cameraError && (
                  <div className="camera-error-display">
                    <AlertCircle size={16} />
                    <span>{cameraError}</span>
                  </div>
                )}

                {cameraBusyError && (
                  <div className="hint-box" style={{
                    marginTop: 8, padding: '10px 12px',
                    background: 'rgba(255, 200, 0, 0.1)',
                    border: '1px solid rgba(255, 200, 0, 0.3)',
                    borderRadius: 6, fontSize: 13,
                    color: 'var(--text-secondary, #ccc)', lineHeight: 1.5
                  }}>
                    💡 <strong>Tip:</strong> Close video apps (Zoom, Teams, Skype, OBS) or other browser tabs using
                    the camera, then click <strong>Retry</strong>. If using a USB webcam, try unplugging and re-plugging.
                  </div>
                )}
              </div>

              <div className="live-stats-row">
                <div className="live-stats-summary">
                  <div className="live-stat">
                    <span className="live-stat-value">{liveDetections.length}</span>
                    <span className="live-stat-label">This Session</span>
                  </div>
                  <div className="live-stat">
                    <span className="live-stat-value">{liveData.total || 0}</span>
                    <span className="live-stat-label">Total</span>
                  </div>
                  <div className="live-stat">
                    <span className="live-stat-value">{isMonitoring ? 'ON' : 'OFF'}</span>
                    <span className="live-stat-label">Camera</span>
                  </div>
                </div>

                <div className="live-session-detections">
                  <h3>
                    <Camera size={16} />
                    Camera Detections
                    {isMonitoring && <span className="live-badge-small">LIVE</span>}
                  </h3>
                  {liveDetections.length > 0 ? (
                    <div className="live-detections-list live-detections-scroll">
                      {liveDetections.map((detection, index) => (
                        <div key={detection.id || index} className="live-detection-item live-item">
                          <div className="detection-info">
                            <span className="detection-plate">{detection.plate_number}</span>
                            <span className="detection-state badge">{detection.state}</span>
                          </div>
                          <div className="detection-meta">
                            <span className="detection-confidence">
                              {formatConfidence(detection.confidence)}
                            </span>
                            <span className="detection-time">
                              {new Date(detection.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="camera-empty-state-small">
                      <Camera size={24} />
                      <p>No plates confirmed yet</p>
                      <span>Plates need {VOTE_THRESHOLD} matching reads</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary"
                onClick={() => { setShowLiveModal(false); fetchDashboardData(); }}>
                Close
              </button>
              <button className="btn btn-primary" onClick={fetchLiveData} disabled={loading}>
                {loading ? 'Refreshing...' : 'Refresh Data'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
