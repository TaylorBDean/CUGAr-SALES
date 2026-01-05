/**
 * CUGAr-SALES Desktop Application
 * Electron main process for local sales assistant deployment
 */

const { app, BrowserWindow, ipcMain, Tray, Menu, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');

// Backend process reference
let backendProcess = null;
let mainWindow = null;
let tray = null;

// Configuration
const BACKEND_PORT = 8000;
const FRONTEND_PORT = 3000;
const isDev = process.env.NODE_ENV === 'development';

/**
 * Start Python backend server
 */
function startBackend() {
  const pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';
  const projectRoot = path.join(__dirname, '../../..');
  
  console.log('[Backend] Starting CUGAr backend...');
  
  backendProcess = spawn(pythonExecutable, [
    '-m', 'uvicorn',
    'cuga.backend.server.main:app',
    '--host', '127.0.0.1',
    '--port', BACKEND_PORT.toString(),
    '--log-level', 'info'
  ], {
    cwd: projectRoot,
    env: { ...process.env, PYTHONUNBUFFERED: '1' }
  });

  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data.toString().trim()}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend] ${data.toString().trim()}`);
  });

  backendProcess.on('error', (error) => {
    console.error('[Backend] Failed to start:', error);
  });

  backendProcess.on('exit', (code) => {
    console.log(`[Backend] Exited with code ${code}`);
    backendProcess = null;
  });
}

/**
 * Stop Python backend server
 */
function stopBackend() {
  if (backendProcess) {
    console.log('[Backend] Stopping...');
    backendProcess.kill();
    backendProcess = null;
  }
}

/**
 * Check if first run and launch setup wizard
 */
function checkFirstRun() {
  const projectRoot = path.join(__dirname, '../../..');
  const envFile = path.join(projectRoot, '.env.sales');
  
  if (!fs.existsSync(envFile)) {
    console.log('[Setup] First run detected, launching setup wizard...');
    
    const pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';
    const wizardProcess = spawn(pythonExecutable, [
      '-m', 'cuga.frontend.setup_wizard'
    ], {
      cwd: projectRoot,
      stdio: 'inherit'
    });
    
    return new Promise((resolve) => {
      wizardProcess.on('exit', (code) => {
        if (code === 0) {
          console.log('[Setup] Wizard completed successfully');
        } else {
          console.log('[Setup] Wizard exited with code', code);
        }
        resolve();
      });
    });
  }
  return Promise.resolve();
}

/**
 * Create main application window
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    title: 'CUGAr Sales Assistant',
    backgroundColor: '#161616', // Carbon theme dark background
    icon: path.join(__dirname, 'public/icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // Load the app
  const startUrl = isDev
    ? `http://localhost:${FRONTEND_PORT}`
    : `file://${path.join(__dirname, 'dist/index.html')}`;

  mainWindow.loadURL(startUrl);

  // Open DevTools in development
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Handle window close
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
    return false;
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * Create system tray
 */
function createTray() {
  const iconPath = path.join(__dirname, 'public/tray-icon.png');
  tray = new Tray(iconPath);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show CUGAr Sales',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Backend Status',
      enabled: false
    },
    {
      label: backendProcess ? '✓ Running' : '✗ Stopped',
      enabled: false
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('CUGAr Sales Assistant');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

/**
 * App lifecycle
 */
app.whenReady().then(async () => {
  console.log('[App] Starting CUGAr Sales Assistant...');
  
  // Check and run setup wizard if needed
  await checkFirstRun();
  
  // Start backend
  startBackend();
  
  // Wait for backend to be ready (simple delay, could be improved with health check)
  await new Promise(resolve => setTimeout(resolve, 3000));
  
  // Create window and tray
  createWindow();
  createTray();
  
  console.log('[App] Ready!');
});

// Quit when all windows are closed (except on macOS)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// On macOS, re-create window when dock icon is clicked
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  } else if (mainWindow) {
    mainWindow.show();
  }
});

// Clean up on quit
app.on('before-quit', () => {
  app.isQuitting = true;
  stopBackend();
});

app.on('will-quit', () => {
  stopBackend();
});

// IPC handlers
ipcMain.handle('get-backend-status', () => {
  return {
    running: backendProcess !== null,
    port: BACKEND_PORT
  };
});

ipcMain.handle('open-external-link', (event, url) => {
  shell.openExternal(url);
});

// Error handling
process.on('uncaughtException', (error) => {
  console.error('[App] Uncaught exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('[App] Unhandled rejection at:', promise, 'reason:', reason);
});
