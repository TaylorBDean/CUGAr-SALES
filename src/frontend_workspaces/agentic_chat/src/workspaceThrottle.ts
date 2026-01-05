// Global fetch interceptor to enforce throttling on workspace API calls
// This is a safety net to catch any direct fetch calls that bypass the service

let lastWorkspaceApiCall = 0;
const MIN_INTERVAL = 3000; // 3 seconds

// Store the original fetch
const originalFetch = window.fetch;

// Override fetch globally
window.fetch = function(...args: Parameters<typeof fetch>): ReturnType<typeof fetch> {
  const [resource] = args;
  const url = typeof resource === 'string' ? resource : resource.url;
  
  // Check if this is a workspace tree API call
  if (url.includes('/api/workspace/tree')) {
    const now = Date.now();
    const timeSinceLastCall = now - lastWorkspaceApiCall;
    
    // If called too soon, reject the request
    if (timeSinceLastCall < MIN_INTERVAL) {
      const remainingTime = MIN_INTERVAL - timeSinceLastCall;
      console.warn(
        `⚠️ Workspace API throttled! Request blocked. ` +
        `Last call was ${timeSinceLastCall}ms ago. ` +
        `Minimum interval is ${MIN_INTERVAL}ms. ` +
        `Wait ${remainingTime}ms before next call.`
      );
      
      // Return a rejected promise with a clear error
      return Promise.reject(new Error(
        `Workspace API call throttled. Wait ${remainingTime}ms before retrying.`
      ));
    }
    
    // Update last call time
    lastWorkspaceApiCall = now;
    console.log(`✅ Workspace API call allowed (${timeSinceLastCall}ms since last call)`);
  }
  
  // Call original fetch
  return originalFetch.apply(this, args);
};

export {}; // Make this a module





