  import React, { useState, useCallback, useRef } from 'react';
import './App.css';
import { Camera, Video, Activity, FileText, Play, Upload, X, CheckCircle, AlertCircle, Info, Moon, Sun, Car, Download, RotateCcw, Menu, RefreshCw } from 'lucide-react';

// ==================== API CONFIGURATION ====================
// Backend server URL - ensure Flask backend is running on port 5000
// Using localhost instead of 127.0.0.1 for better browser compatibility
const API_BASE_URL = 'http://localhost:5000';

// ==================== POLLING INTERVAL FOR LIVE MONITORING ====================
const LIVE_POLL_INTERVAL = 2000; // Poll every 2 seconds for live data updates

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
  const [showLiveModal, setShowLiveModal] = useState(false); // Live monitoring modal state
  const [liveData, setLiveData] = useState({ recent: [], live_detections: [], total: 0, timestamp: null });
  const [connectionStatus, setConnectionStatus] = useState('checking'); // checking, connected, disconnected
  const [toast, setToast] = useState(null);
  const [darkMode, setDarkMode] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    // Check screen size - only for large desktops (1024px+) do we always want open
    const screenWidth = window.innerWidth;
    if (screenWidth >= 1024) return true; // Always open on desktop (1024px+)
    
    // For tablet/mobile (below 1024px), default to collapsed
    return false;
  });
  const [activeSection, setActiveSection] = useState('home');
  const [processingCount, setProcessingCount] = useState(0);
  const [processingStatus, setProcessingStatus] = useState(null);
  
  // ==================== LIVE CAMERA MONITORING STATE ====================
  const [isMonitoring, setIsMonitoring] = useState(false);         // Toggle monitoring on/off
  const [cameraStream, setCameraStream] = useState(null);         // Camera video stream
  const [cameraError, setCameraError] = useState('');              // Camera error message
  const [liveDetections, setLiveDetections] = useState([]);        // Session detections from camera
  const [isProcessingFrame, setIsProcessingFrame] = useState(false); // Processing indicator
  const [cameraStatus, setCameraStatus] = useState('idle');       // idle, starting, active, error, stopping
  
  // Refs for live camera monitoring
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const captureIntervalRef = useRef(null);
  const cameraStreamRef = useRef(null); // Track stream in ref to avoid stale closures
  
  // Ref for live monitoring polling interval
  const livePollingRef = useRef(null);
  
  // ==================== TOAST NOTIFICATION ====================
  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  }, []);

  // ==================== LIVE CAMERA FUNCTIONS ====================
  
  // Start camera stream with fallback for mobile devices
  const startCamera = async () => {
    setCameraStatus('starting');
    setCameraError('');
    
    try {
      console.log('Requesting camera access...');
      
      let stream = null;
      
      // Try rear camera first (for mobile devices)
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
            facingMode: { ideal: 'environment' } // Prefer back/rear camera on mobile
          },
          audio: false
        });
        console.log('Camera stream obtained (rear camera):', stream);
      } catch (rearError) {
        console.log('Rear camera not available, trying front camera...');
        // Fallback to front camera
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
            facingMode: 'user' // Front camera fallback
          },
          audio: false
        });
        console.log('Camera stream obtained (front camera):', stream);
      }
      
      // Last resort: try any camera
      if (!stream) {
        console.log('Trying any available camera...');
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false
        });
        console.log('Camera stream obtained (any camera):', stream);
      }
      
      // Store stream in ref first (to avoid stale closures)
      cameraStreamRef.current = stream;
      
      // Update state
      setCameraStream(stream);
      setIsMonitoring(true);
      
      // Attach stream to video element
      if (videoRef.current) {
        console.log('Attaching stream to video element...');
        videoRef.current.srcObject = stream;
        
        // Wait for video element to be ready and play
        await videoRef.current.play().catch(err => {
          console.error('Video play error:', err);
        });
        console.log('Video started playing');
      } else {
        console.log('Video element not ready yet, will use useEffect');
      }
      
      // Set status to active (this triggers useEffect to ensure video is attached)
      setCameraStatus('active');
      
      // Start capturing frames
      startFrameCapture();
      
      showToast('Camera started successfully', 'success');
    } catch (err) {
      console.error('Camera error:', err);
      setCameraStatus('error');
      cameraStreamRef.current = null;
      
      if (err.name === 'NotAllowedError') {
        setCameraError('Camera access denied. Please allow camera permissions.');
        showToast('Camera access denied', 'error');
      } else if (err.name === 'NotFoundError') {
        setCameraError('No camera found on this device.');
        showToast('No camera found', 'error');
      } else {
        setCameraError('Failed to access camera: ' + err.message);
        showToast('Camera error', 'error');
      }
    }
  };
  
  // Stop camera stream
  const stopCamera = () => {
    setCameraStatus('stopping');
    
    // Clear capture interval
    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current);
      captureIntervalRef.current = null;
    }
    
    // Stop all tracks in the stream
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
      setCameraStream(null);
    }
    
    // Reset video element
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    
    setIsMonitoring(false);
    setCameraStatus('idle');
    showToast('Camera stopped', 'info');
  };
  
  // Capture frame from video and send to backend using /process_frame endpoint
  const captureAndSendFrame = async () => {
    if (!videoRef.current || !canvasRef.current || isProcessingFrame) return;
    
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    // Ensure video is ready
    if (video.readyState !== 4) return;
    
    // Set canvas dimensions to match video
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    // Draw current video frame to canvas
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Convert canvas to blob for multipart/form-data upload
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 1.0));
    
    if (!blob) {
      console.error('Failed to create blob from canvas');
      return;
    }
    
    console.log('Sending frame to backend (size:', blob.size, 'bytes)');
    setIsProcessingFrame(true);
    
    try {
      // Create FormData with the frame as a file
      const formData = new FormData();
      formData.append('frame', blob, 'frame.jpg');
      
      const response = await fetch(`${API_BASE_URL}/api/image`, {
        method: 'POST',
        body: formData
        // Note: NOT setting Content-Type header - let browser set it with boundary for FormData
      });
      
      console.log('API Response status:', response.status);
      
      if (response.ok) {
        // Update connection status to connected on successful response
        setConnectionStatus('connected');
        
        const data = await response.json();
        console.log('API Response data:', data);
        
        if (data.detections && data.detections.length > 0) {
          console.log('Detected plates:', data.plates);
          
          // Add new detections to the list (prevent duplicates)
          setLiveDetections(prev => {
            const newDetections = [...prev];
            const existingPlates = new Set(newDetections.map(d => d.plate_number));
            
            data.detections.forEach(detection => {
              if (!existingPlates.has(detection.plate_number)) {
                newDetections.unshift({
                  ...detection,
                  timestamp: new Date().toISOString(),
                  id: Date.now() + Math.random()
                });
              }
            });
            
            // Keep only last 50 detections
            return newDetections.slice(0, 50);
          });
          
          showToast(`Detected: ${data.plates.join(', ')}`, 'success');
        }
        
        // Also update logged plates if available
        if (data.logged_plates && data.logged_plates.length > 0) {
          console.log('Total logged plates:', data.logged_plates.length);
        }
      } else {
        console.error('Failed to process frame:', response.status);
        const errorText = await response.text();
        console.error('Error response:', errorText);
        setConnectionStatus('disconnected');
      }
    } catch (err) {
      console.error('Frame processing error:', err);
      setConnectionStatus('disconnected');
    } finally {
      setIsProcessingFrame(false);
    }
  };
  
  // Start capturing frames at regular intervals (500ms as per requirements)
  const startFrameCapture = () => {
    // Clear any existing interval
    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current);
    }
    
    // Capture frames every 500ms as per requirements
    captureIntervalRef.current = setInterval(captureAndSendFrame, 500);
  };
  
  // Handle live monitoring toggle
  const toggleMonitoring = () => {
    if (isMonitoring) {
      stopCamera();
    } else {
      startCamera();
    }
  };
  
  // ==================== CAMERA VIDEO INITIALIZATION EFFECT ====================
  // This effect handles video element initialization when cameraStatus changes to 'active'
  // and ensures the stream is properly attached even if the video element wasn't ready initially
  React.useEffect(() => {
    if (cameraStatus === 'active' && videoRef.current && cameraStreamRef.current) {
      // If video element exists but srcObject is not set, attach it
      if (!videoRef.current.srcObject) {
        console.log('useEffect: Attaching stream to video element...');
        videoRef.current.srcObject = cameraStreamRef.current;
        videoRef.current.play().catch(err => {
          console.error('Video play error in useEffect:', err);
        });
      }
    }
  }, [cameraStatus]);
  
  // Cleanup when modal closes - use refs to avoid stale closures
  React.useEffect(() => {
    if (!showLiveModal) {
      console.log('Modal closed, cleaning up camera...');
      
      // Clear capture interval
      if (captureIntervalRef.current) {
        clearInterval(captureIntervalRef.current);
        captureIntervalRef.current = null;
      }
      
      // Stop all tracks in the stream using ref (avoids stale closure issue)
      if (cameraStreamRef.current) {
        cameraStreamRef.current.getTracks().forEach(track => track.stop());
        cameraStreamRef.current = null;
      }
      
      // Reset video element
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
      
      // Reset all state
      setCameraStream(null);
      setIsMonitoring(false);
      setCameraStatus('idle');
      setLiveDetections([]);
      setCameraError('');
    }
  }, [showLiveModal]);
  
  // ==================== CONNECTION TEST ====================
  // Tests connectivity to the backend server
  const testConnection = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/image`, {
        method: 'OPTIONS'
      });
      if (response.ok) {
        setConnectionStatus('connected');
      } else {
        setConnectionStatus('disconnected');
      }
    } catch (err) {
      console.error('Connection test failed:', err);
      setConnectionStatus('disconnected');
    }
  };

  // ==================== FETCH DASHBOARD DATA ====================
  // Fetches dashboard statistics from the backend
  const fetchDashboardData = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/dashboard`);
      if (response.ok) {
        const data = await response.json();
        setDashboardData(data);
      } else {
        console.error('Failed to fetch dashboard data:', response.status);
      }
    } catch (err) {
      console.error('Dashboard fetch error:', err);
      // Silently fail - use default stats when backend is unavailable
      setDashboardData(null);
    }
  };

  // ==================== FETCH LIVE DATA ====================
  // Fetches live detection data for real-time monitoring
  const fetchLiveData = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/live-data`);
      if (response.ok) {
        const data = await response.json();
        setLiveData(data);
        setConnectionStatus('connected');
      } else {
        console.error('Failed to fetch live data:', response.status);
        setConnectionStatus('disconnected');
      }
    } catch (err) {
      console.error('Live data fetch error:', err);
      setConnectionStatus('disconnected');
    } finally {
      setLoading(false);
    }
  };

  // ==================== LIVE MONITORING POLLING ====================
  // Start/stop polling when live modal opens/closes
  React.useEffect(() => {
    if (showLiveModal) {
      // Start polling when modal opens
      fetchLiveData(); // Fetch immediately
      livePollingRef.current = setInterval(fetchLiveData, LIVE_POLL_INTERVAL);
    } else {
      // Stop polling when modal closes
      if (livePollingRef.current) {
        clearInterval(livePollingRef.current);
        livePollingRef.current = null;
      }
    }
    
    // Cleanup on unmount
    return () => {
      if (livePollingRef.current) {
        clearInterval(livePollingRef.current);
      }
    };
  }, [showLiveModal]);

  // ==================== INITIAL DATA FETCH ====================
  React.useEffect(() => {
    // Fetch dashboard data on mount
    fetchDashboardData();
    // Test connection to backend
    testConnection();
  }, []);

  // ==================== THEME MANAGEMENT ====================
  React.useEffect(() => {
    if (darkMode) {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }, [darkMode]);

  // ==================== RESET HANDLER ====================
  // Reset all state to initial values
  const handleReset = () => {
    setResults([]);
    setDashboardData(null);
    setFiles([]);
    setUploadProgress(0);
    setError('');
    setShowUploadPanel(false);
    setShowErrorModal(false);
    setActiveSection('home');
    fetchDashboardData();
    showToast('Dashboard reset successfully', 'success');
  };

  // ==================== EXPORT ANALYTICS HANDLER ====================
  // Export analytics data with duplicate filtering
  const handleExportAnalytics = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/export-analytics`);
      
      if (response.ok) {
        const data = await response.json();
        
        if (data.data && data.data.length > 0) {
          // Transform and display the results
          setResults(data.data.map((item, idx) => ({
            filename: item.Image_Name || item.image_name || `Record ${idx + 1}`,
            status: 'processed',
            plate_number: item.Plate_Number || item.plate_number,
            state_of_origin: item.State_of_Origin || item.state_of_origin,
            confidence: item.Confidence || item.confidence,
            message: 'Exported from analytics'
          })));
          
          // Show summary message including duplicate filtering info
          const duplicatesMsg = data.summary?.duplicates_filtered > 0 
            ? ` (${data.summary.duplicates_filtered} duplicates filtered)` 
            : '';
          showToast(`Exported ${data.data.length} unique records${duplicatesMsg}`, 'success');
        } else {
          showToast('No analytics data available to export', 'info');
        }
      } else {
        const errorData = await response.json();
        showToast(errorData.error || 'Failed to export analytics', 'error');
      }
    } catch (err) {
      console.error('Export analytics error:', err);
      showToast('Network error. Please check if backend is running.', 'error');
    } finally {
      setLoading(false);
    }
  };

  // ==================== CLEAR LOGS HANDLER ====================
  // Clear all logged plate data by calling backend endpoint
  const handleClearLogs = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/clear-logs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        
        // Clear frontend state
        setResults([]);
        setDashboardData({
          total: 0,
          states: {},
          avg_confidence: 0,
          recent: []
        });
        setFiles([]);
        setUploadProgress(0);
        setLiveDetections([]);
        
        // Refresh dashboard to show cleared stats
        fetchDashboardData();
        
        showToast(data.message || 'All logs cleared successfully', 'success');
      } else {
        const errorData = await response.json();
        showToast(errorData.message || 'Failed to clear logs', 'error');
      }
    } catch (err) {
      console.error('Clear logs error:', err);
      showToast('Network error occurred while clearing logs', 'error');
    } finally {
      setLoading(false);
    }
  };

  // ==================== FILE UPLOAD HANDLER ====================
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
      const formData = new FormData();
      
      // Append all files with the key 'file' (required by backend)
      // This allows multiple files to be sent in a single request
      files.forEach((file) => {
        formData.append('file', file);
      });

      setUploadProgress(5); // Preparing upload
      setProcessingStatus('Preparing upload...');

      // Determine endpoint based on upload type (image or video)
      const endpoint = uploadType === 'image' ? '/api/image' : '/api/video';
      
      // Simulate progress for upload phase
      const uploadProgressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev < 25) return prev + 5;
          return prev;
        });
      }, 200);
      
      setProcessingStatus('Uploading file(s)...');

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        body: formData,
        // Note: NOT setting Content-Type header manually - let browser set it with boundary for FormData
      });

      clearInterval(uploadProgressInterval);
      setUploadProgress(30);
      setProcessingStatus(uploadType === 'image' ? 'Detecting license plates...' : 'Processing video frames...');

      if (response.ok) {
        const data = await response.json();
        
        setUploadProgress(80);
        setProcessingStatus('OCR processing...');
        
        // Simulate OCR progress
        const ocrProgressInterval = setInterval(() => {
          setUploadProgress(prev => {
            if (prev < 95) return prev + 3;
            return prev;
          });
        }, 100);
        
        // Small delay to show OCR processing
        await new Promise(resolve => setTimeout(resolve, 300));
        clearInterval(ocrProgressInterval);
        
        setUploadProgress(100);
        setProcessingStatus('Complete!');
        
        if (uploadType === 'image') {
          // For image uploads, response contains { status, total_files, processed_count, not_found_count, results: [...] }
          const allResults = data.results || [];
          setResults(allResults);
          
          const successCount = data.processed_count || 0;
          const notFoundCount = data.not_found_count || 0;
          
          if (successCount > 0) {
            showToast(`Successfully processed ${successCount} of ${data.total_files} images!`, 'success');
          } else if (notFoundCount > 0) {
            showToast(`No license plates found in ${notFoundCount} images`, 'info');
          } else {
            showToast('Processing complete, but no plates detected', 'info');
          }
        } else {
          // For video uploads, extract individual plate detections from data.results
          const videoResults = data.results || [];
          
          // Add frame info to each result for display
          const enhancedResults = videoResults.map(result => ({
            ...result,
            filename: result.filename || data.filename,
            frame_info: result.filename ? `Frame: ${result.filename.split('_frame_')[1] || 'N/A'}` : undefined
          }));
          
          setResults(enhancedResults);
          
          if (data.status === 'processed') {
            showToast(`Video processed! Found ${data.plates_found || 0} plate(s)`, 'success');
          } else if (videoResults.length === 0) {
            showToast('Video processed, but no plates found', 'info');
          }
        }
        
        // Refresh dashboard after successful upload
        fetchDashboardData();
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Upload failed');
        setShowErrorModal(true);
        showToast('Failed to process files', 'error');
      }
    } catch (err) {
      console.error('Upload error:', err);
      setError('Network error occurred. Please check if the backend server is running at http://localhost:5000');
      setShowErrorModal(true);
      showToast('Network error occurred', 'error');
    } finally {
      setLoading(false);
      // Reset processing status after a short delay
      setTimeout(() => {
        if (!loading) setProcessingStatus(null);
      }, 1000);
    }
  };

  // ==================== ACTION HANDLER ====================
  // Handles various action buttons (image, video, live, etc.)
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
        // Open live monitoring modal
        setShowLiveModal(true);
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

  // ==================== FORMAT FILE SIZE ====================
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // ==================== DASHBOARD DATA MAPPING ====================
  // Map backend response to frontend expected format
  // Backend returns: { total, states, avg_confidence, recent }
  // Frontend expects: { total_detections, today_detections, accuracy_rate, states_covered }
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
    // No data yet - show placeholder values
    return {
      total_detections: 0,
      today_detections: 0,
      accuracy_rate: null,
      states_covered: 0,
      hasData: false
    };
  }, [dashboardData]);

  // ==================== RENDER ====================
  return (
    <div className={`App ${darkMode ? 'dark-mode' : ''}`}>
      {/* Toast Notification */}
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

      {/* Mobile Menu Button */}
      <button 
        className={`mobile-menu-btn ${sidebarOpen ? 'hidden' : ''}`}
        onClick={() => setSidebarOpen(true)}
        aria-label="Open menu"
      >
        <Menu size={24} />
      </button>

      {/* Sidebar Overlay */}
      <div 
        className={`sidebar-overlay ${sidebarOpen ? 'visible' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : 'collapsed'}`}>
        <div className="sidebar-header">
          <div className="logo">
            <img src={require('./imageCapture.jpeg')} alt="AVLPRDL" style={{ width: 32, height: 32, borderRadius: 8 }} />
            <span>AVLPRDL System</span>
          </div>
        </div>
        
        <button className="sidebar-expand" onClick={() => setSidebarOpen(true)}>
          <img src={require('./imageCapture.jpeg')} alt="AVLPRDL" style={{ width: 32, height: 32,}} />
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
            <span>{darkMode ? '' : ''}</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className={`main-content ${sidebarOpen ? '' : 'full-width'}`}>
        <header className="top-header">
          <div className="header-left">
            <h1>Automated Vehicle License Plate Recognition (AVLPR)<br />& Data Logging</h1>
            <p>Real-Time Detection & Intelligent Data Archiving</p>
          </div>
          
        </header>

        {/* Stats Cards */}
        <section className="stats-section">
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon stat-icon-1">
                <Camera size={24} />
              </div>
              <div className="stat-content">
                <span className="stat-value">{stats.today_detections}</span>
                <span className="stat-label">Recent Detections</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon stat-icon-2">
                <Activity size={24} />
              </div>
              <div className="stat-content">
                <span className="stat-value">{stats.total_detections}</span>
                <span className="stat-label">Total Plates</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon stat-icon-3">
                <CheckCircle size={24} />
              </div>
              <div className="stat-content">
                <span className="stat-value">{stats.hasData ? `${stats.accuracy_rate}%` : '--'}</span>
                <span className="stat-label">Accuracy Rate</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon stat-icon-4">
                <FileText size={24} />
              </div>
              <div className="stat-content">
                <span className="stat-value">{stats.states_covered}</span>
                <span className="stat-label">States Covered</span>
              </div>
            </div>
          </div>
        </section>

        {/* Action Cards */}
        <section className="actions-section">
          <h2>Quick Actions</h2>
          <div className="actions-grid">
            <button className="action-card action-image" onClick={() => handleAction('image')}>
              <div className="action-icon">
                <Camera size={32} />
              </div>
              <div className="action-info">
                <h3>Process Image</h3>
                <p>Upload and analyze image files</p>
              </div>
              <div className="action-arrow">
                <Upload size={20} />
              </div>
            </button>

            <button className="action-card action-video" onClick={() => handleAction('video')}>
              <div className="action-icon">
                <Video size={32} />
              </div>
              <div className="action-info">
                <h3>Analyze Video</h3>
                <p>Process video streams</p>
              </div>
              <div className="action-arrow">
                <Upload size={20} />
              </div>
            </button>

            <button className="action-card action-live" onClick={() => handleAction('live')}>
              <div className="action-icon">
                <Play size={32} />
              </div>
              <div className="action-info">
                <h3>Live Monitoring</h3>
                <p>Real-Time Detection</p>
              </div>
              <div className="action-arrow">
                <Play size={20} />
              </div>
            </button>
          </div>
        </section>

        {/* Results Section - Only show successfully processed plates */}
        {(() => {
          // Filter results into readable and unread
          const readableResults = results.filter(r => r.status === 'processed');
          const unreadResults = results.filter(r => r.status !== 'processed');
          
          return (
            <>
              {readableResults.length > 0 && (
                <section className="results-section">
                  <h2>Detection Results</h2>
                  <div className="results-grid">
                    {readableResults.map((result, index) => (
                      <div key={index} className="result-card">
                        <div className="result-header">
                          <span className="result-filename">{result.filename}</span>
                          <span className={`result-status ${result.status}`}>{result.status}</span>
                        </div>
                        <div className="result-body">
                          <p className="result-message">{result.message}</p>
                          {result.plate_number && (
                            <div className="plate-details">
                              <div className="plate-number">
                                <span className="label">Plate Number</span>
                                <span className="value">{result.plate_number}</span>
                              </div>
                              <div className="plate-state">
                                <span className="label">State</span>
                                <span className="value badge">{result.state_of_origin}</span>
                              </div>
                              <div className="plate-confidence">
                                <span className="label">Confidence</span>
                                <span className="value">{result.confidence}%</span>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
              
              {/* Unread Plates Summary - Shown at bottom when plates couldn't be read */}
              {unreadResults.length > 0 && (
                <section className="unread-plates-section">
                  <h3>
                    <AlertCircle size={20} />
                    Unread Plates ({unreadResults.length})
                  </h3>
                  <div className="unread-plates-list">
                    {unreadResults.map((result, index) => (
                      <span key={index} className="unread-plate-tag">
                        {result.filename || `File ${index + 1}`}
                      </span>
                    ))}
                  </div>
                </section>
              )}
            </>
          );
        })()}

        <footer className="app-footer">
          <div className="footer-left">
            <img src="/MYLogo.png" alt="wurdboss" width={25}/>
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
                {uploadType === 'image' ? <><Camera size={24} /> Upload Images</> : <><Video size={24} /> Upload Video</>}
              </h2>
              <button className="modal-close" onClick={() => setShowUploadPanel(false)}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleFileUpload} className="upload-form">
              <div className="file-drop-zone">
                <Upload size={48} />
                <p>Drag and drop or click to select {uploadType === 'image' ? 'multiple images' : 'a video'}</p>
                <input
                  type="file"
                  multiple={uploadType === 'image'}
                  accept={uploadType === 'image' ? '.png,.jpg,.jpeg,.gif,.bmp' : '.mp4,.avi,.mov,.mkv'}
                  onChange={(e) => {
                    const newFiles = Array.from(e.target.files);
                    setFiles(prev => [...prev, ...newFiles]);
                  }}
                />
              </div>
              {files.length > 0 && (
                <div className="selected-files">
                  <div className="selected-files-header">
                    <span>Selected Files ({files.length})</span>
                    <button 
                      type="button" 
                      className="clear-all-btn"
                      onClick={() => setFiles([])}
                    >
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
                          onClick={() => setFiles(prev => prev.filter((_, i) => i !== index))}
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
                    <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
                  </div>
                  <span className="progress-text">
                    {processingStatus || `Processing ${processingCount} of ${files.length} files...`}
                  </span>
                </div>
              )}
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => {
                  setShowUploadPanel(false);
                  setFiles([]);
                }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={loading || files.length === 0}>
                  {loading ? 'Processing...' : `Upload ${files.length > 0 ? `${files.length} ` : ''}${uploadType === 'image' ? 'Image(s)' : 'Video'}`}
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
              <button className="btn btn-secondary" onClick={() => { setShowErrorModal(false); setError(''); }}>
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
              <div className="about-hero">
                <h3>AVLPRDL System</h3>
              </div>
              
              <div className="about-details">
                <div className="about-item">
                  <span className="about-label">Project Topic</span>
                  <span className="about-value">Developing a Solution for Automated Vehicle License Plate Recognition (AVLPR) & Data Logging</span>
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

      {/* ==================== LIVE MONITORING MODAL ==================== */}
      {/* Enhanced Live Monitoring with camera and real-time detection */}
      {showLiveModal && (
        <div className="modal-overlay" onClick={() => setShowLiveModal(false)}>
          <div className="modal live-modal live-modal-extra-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2><Activity size={24} /> Live Monitoring</h2>
              <div className="live-status-indicator">
                <span className={`live-dot ${connectionStatus === 'connected' ? 'active' : ''}`}></span>
                <span className={`live-status-text ${connectionStatus === 'connected' ? 'connected' : ''}`}>{connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}</span>
              </div>
              <button className="modal-close" onClick={() => setShowLiveModal(false)}>
                <X size={20} />
              </button>
            </div>
            
            <div className="live-content">
              {/* Hidden canvas for frame capture */}
              <canvas ref={canvasRef} style={{ display: 'none' }} />
              
              {/* Camera Section */}
              <div className="live-camera-section">
                
                <div className="camera-preview-wrapper">
                  {cameraStatus === 'idle' && (
                    <div className="camera-placeholder">
                      <Camera size={48} />
                     
                    </div>
                  )}
                  {cameraStatus === 'starting' && (
                    <div className="camera-loading">
                      <RefreshCw size={32} className="spin" />
                      <p>Starting camera...</p>
                    </div>
                  )}
                  {cameraStatus === 'active' && (
                    <video
                      ref={videoRef}
                      className="camera-video"
                      autoPlay
                      playsInline
                      muted
                    />
                  )}
                  {cameraStatus === 'error' && (
                    <div className="camera-placeholder camera-error-state">
                      <AlertCircle size={48} />
                      <p>Camera Error</p>
                      <span>{cameraError}</span>
                    </div>
                  )}
                  {cameraStatus === 'stopping' && (
                    <div className="camera-loading">
                      <RefreshCw size={32} className="spin" />
                      <p>Stopping camera...</p>
                    </div>
                  )}
                </div>
                
                {/* Camera Controls */}
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
                      <>
                        <X size={18} />
                        Stop Monitoring
                      </>
                    ) : (
                      <>
                        <Play size={18} />
                        Start Monitoring
                      </>
                    )}
                  </button>
                  {isProcessingFrame && (
                    <div className="camera-processing-indicator">
                      <RefreshCw size={16} className="spin" />
                      <span>Processing...</span>
                    </div>
                  )}
                </div>
                
                {/* Camera Error Display */}
                {cameraError && (
                  <div className="camera-error-display">
                    <AlertCircle size={16} />
                    <span>{cameraError}</span>
                  </div>
                )}
              </div>
              
              {/* Stats and Detection Results Row */}
              <div className="live-stats-row">
                {/* Live Detection Stats */}
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
                
                {/* Session Detections */}
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
                            <span className="detection-confidence">{detection.confidence?.toFixed(1)}%</span>
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
                      <p>No plates detected yet</p>
                      <span>Point camera at vehicles</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => {
                setShowLiveModal(false);
                fetchDashboardData();
              }}>
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
