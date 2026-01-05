import { UserType } from "@carbon/ai-chat";

// Declare process for webpack environment variable injection
declare const process: {
  env: {
    REACT_APP_API_URL?: string;
  };
} | undefined;

export const RESPONSE_USER_PROFILE = {
  id: "ai-chatbot-user",
  userName: "CUGA",
  fullName: "CUGA Agent",
  displayName: "CUGA",
  accountName: "CUGA Agent",
  replyToId: "ai-chatbot-user",
  userType: UserType.BOT,
};

// Get the base URL for the backend API
// In production (HF Spaces), use the current origin
// In development, use localhost with port 7860 (default port)
export const getApiBaseUrl = (): string => {
  // If running in Hugging Face Spaces or production, use current origin
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // Check if we're on HF Spaces or not localhost
    if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
      return window.location.origin;
    }
  }
  
  // Default to localhost:7860 for local development
  // This can be overridden by setting REACT_APP_API_URL environment variable
  // Note: In browser, process.env is injected by webpack at build time
  if (typeof process !== 'undefined' && process?.env?.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }
  
  return 'http://localhost:7860';
};

export const API_BASE_URL = getApiBaseUrl();
