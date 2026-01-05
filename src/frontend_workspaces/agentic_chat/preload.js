/**
 * Electron preload script
 * Safely exposes backend APIs to renderer process
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Get backend server status
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  
  // Open external links
  openExternal: (url) => ipcRenderer.invoke('open-external-link', url),
  
  // Platform info
  platform: process.platform,
  version: process.versions.electron
});
