/**
 * Keyboard Shortcuts Hook
 * Handles global keyboard shortcuts for the application
 */

import { useEffect } from 'react';

interface KeyboardShortcut {
  key: string;
  ctrlOrCmd?: boolean;
  shift?: boolean;
  alt?: boolean;
  handler: () => void;
  description: string;
}

export const useKeyboardShortcuts = (shortcuts: KeyboardShortcut[]) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      for (const shortcut of shortcuts) {
        const ctrlOrCmdMatch = shortcut.ctrlOrCmd
          ? (event.ctrlKey || event.metaKey)
          : true;
        const shiftMatch = shortcut.shift ? event.shiftKey : !event.shiftKey;
        const altMatch = shortcut.alt ? event.altKey : !event.altKey;
        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase();

        if (ctrlOrCmdMatch && shiftMatch && altMatch && keyMatch) {
          event.preventDefault();
          shortcut.handler();
          break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
};

// Predefined shortcuts
export const DEFAULT_SHORTCUTS = {
  QUICK_ACTIONS: { key: 'k', ctrlOrCmd: true, description: 'Open Quick Actions' },
  NEW_CHAT: { key: 'n', ctrlOrCmd: true, description: 'New Chat' },
  TOGGLE_SIDEBAR: { key: 'b', ctrlOrCmd: true, description: 'Toggle Sidebar' },
  EXPORT: { key: 'e', ctrlOrCmd: true, description: 'Export Results' },
  HELP: { key: '/', ctrlOrCmd: true, description: 'Show Help' },
};
