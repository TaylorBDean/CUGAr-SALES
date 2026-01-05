/**
 * Profile Selector Component
 * Switch between sales profiles (AGENTS.md compliant)
 */

import React, { useState, useEffect } from 'react';
import { ChevronDown, User, CheckCircle, AlertCircle } from 'lucide-react';

export interface SalesProfile {
  id: string;
  name: string;
  description: string;
  color: string;
  icon?: string;
}

const DEFAULT_PROFILES: SalesProfile[] = [
  {
    id: 'enterprise',
    name: 'Enterprise',
    description: 'Strategic deals, long sales cycles, executive engagement',
    color: '#8b5cf6'
  },
  {
    id: 'smb',
    name: 'SMB',
    description: 'Velocity-focused, transactional, high volume',
    color: '#0f62fe'
  },
  {
    id: 'technical',
    name: 'Technical Specialist',
    description: 'Pre-sales, POCs, technical validation',
    color: '#059669'
  }
];

interface ProfileSelectorProps {
  onProfileChange?: (profileId: string) => void;
  compact?: boolean;
}

export const ProfileSelector: React.FC<ProfileSelectorProps> = ({ 
  onProfileChange,
  compact = false
}) => {
  const [currentProfile, setCurrentProfile] = useState<SalesProfile>(DEFAULT_PROFILES[0]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Load current profile from backend or localStorage
    const savedProfileId = localStorage.getItem('cuga_profile');
    if (savedProfileId) {
      const profile = DEFAULT_PROFILES.find(p => p.id === savedProfileId);
      if (profile) setCurrentProfile(profile);
    }
  }, []);

  const handleProfileChange = async (profile: SalesProfile) => {
    setLoading(true);
    setError(null);

    try {
      // Get budget info from new AGENTS.md API
      const response = await fetch(`http://localhost:8000/api/agents/budget/${profile.id}`);

      if (!response.ok) {
        throw new Error('Failed to load profile budget');
      }

      const budgetData = await response.json();
      console.log(`[Profile] Switched to ${profile.name}:`, {
        total_calls: budgetData.total_calls,
        used: budgetData.used_calls,
        utilization: budgetData.utilization
      });

      setCurrentProfile(profile);
      localStorage.setItem('cuga_profile', profile.id);
      
      if (onProfileChange) {
        onProfileChange(profile.id);
      }

      setIsOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      // Still update UI for demo purposes
      setCurrentProfile(profile);
      localStorage.setItem('cuga_profile', profile.id);
      if (onProfileChange) {
        onProfileChange(profile.id);
      }
      setIsOpen(false);
    } finally {
      setLoading(false);
    }
  };

  if (compact) {
    return (
      <div className="profile-selector-compact">
        <div 
          className="current-profile-compact"
          onClick={() => setIsOpen(!isOpen)}
          style={{ borderLeftColor: currentProfile.color }}
        >
          <User size={12} style={{ color: currentProfile.color }} />
          <span className="profile-name">{currentProfile.name}</span>
          <ChevronDown size={12} className={isOpen ? 'rotated' : ''} />
        </div>

        {isOpen && (
          <>
            <div className="dropdown-overlay" onClick={() => setIsOpen(false)} />
            <div className="dropdown-compact">
              {DEFAULT_PROFILES.map(profile => (
                <div
                  key={profile.id}
                  className={`dropdown-item ${profile.id === currentProfile.id ? 'active' : ''}`}
                  onClick={() => handleProfileChange(profile)}
                >
                  <div 
                    className="profile-indicator"
                    style={{ background: profile.color }}
                  />
                  <span className="profile-name">{profile.name}</span>
                  {profile.id === currentProfile.id && (
                    <CheckCircle size={12} style={{ color: profile.color }} />
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        <style jsx>{`
          .profile-selector-compact {
            position: relative;
          }

          .current-profile-compact {
            display: flex;
            align-items: center;
            gap: 0.375rem;
            padding: 0.375rem 0.625rem;
            background: white;
            border: 1px solid #e5e7eb;
            border-left: 3px solid;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.75rem;
            transition: all 0.2s;
          }

          .current-profile-compact:hover {
            background: #f8fafc;
            border-color: #cbd5e1;
          }

          .profile-name {
            font-weight: 500;
            color: #334155;
          }

          .rotated {
            transform: rotate(180deg);
          }

          .dropdown-overlay {
            position: fixed;
            inset: 0;
            z-index: 9998;
          }

          .dropdown-compact {
            position: absolute;
            top: calc(100% + 0.25rem);
            left: 0;
            right: 0;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            z-index: 9999;
            overflow: hidden;
          }

          .dropdown-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.625rem 0.75rem;
            font-size: 0.75rem;
            cursor: pointer;
            transition: background 0.15s;
          }

          .dropdown-item:hover {
            background: #f8fafc;
          }

          .dropdown-item.active {
            background: #eff6ff;
          }

          .profile-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="profile-selector">
      <div className="profile-header">
        <User size={16} />
        <h3 className="profile-title">Sales Profile</h3>
      </div>

      <div className="current-profile" style={{ borderColor: currentProfile.color }}>
        <div className="profile-content">
          <div className="profile-top">
            <span className="profile-label">{currentProfile.name}</span>
            <span 
              className="profile-badge"
              style={{ background: currentProfile.color + '20', color: currentProfile.color }}
            >
              Active
            </span>
          </div>
          <p className="profile-desc">{currentProfile.description}</p>
        </div>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="change-btn"
          disabled={loading}
        >
          {loading ? 'Switching...' : 'Change'}
          <ChevronDown size={14} className={isOpen ? 'rotated' : ''} />
        </button>
      </div>

      {error && (
        <div className="error-message">
          <AlertCircle size={14} />
          <span>{error} (using local mode)</span>
        </div>
      )}

      {isOpen && (
        <>
          <div className="dropdown-overlay" onClick={() => setIsOpen(false)} />
          <div className="profile-dropdown">
            {DEFAULT_PROFILES.map(profile => (
              <div
                key={profile.id}
                className={`profile-option ${profile.id === currentProfile.id ? 'active' : ''}`}
                onClick={() => handleProfileChange(profile)}
                style={{ 
                  borderLeftColor: profile.color,
                  background: profile.id === currentProfile.id ? profile.color + '08' : 'transparent'
                }}
              >
                <div className="option-content">
                  <div className="option-top">
                    <span className="option-name">{profile.name}</span>
                    {profile.id === currentProfile.id && (
                      <CheckCircle size={14} style={{ color: profile.color }} />
                    )}
                  </div>
                  <p className="option-desc">{profile.description}</p>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <style jsx>{`
        .profile-selector {
          background: white;
          border-radius: 8px;
          border: 1px solid #e5e7eb;
          overflow: hidden;
          position: relative;
        }

        .profile-header {
          padding: 0.75rem 1rem;
          border-bottom: 1px solid #e5e7eb;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          background: #f8fafc;
        }

        .profile-title {
          font-size: 0.875rem;
          font-weight: 600;
          color: #1e293b;
          margin: 0;
        }

        .current-profile {
          padding: 1rem;
          border-left: 4px solid;
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 1rem;
        }

        .profile-content {
          flex: 1;
          min-width: 0;
        }

        .profile-top {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          margin-bottom: 0.375rem;
        }

        .profile-label {
          font-weight: 600;
          color: #1e293b;
          font-size: 0.9375rem;
        }

        .profile-badge {
          padding: 0.125rem 0.5rem;
          border-radius: 9999px;
          font-size: 0.6875rem;
          font-weight: 600;
          text-transform: uppercase;
        }

        .profile-desc {
          margin: 0;
          font-size: 0.8125rem;
          color: #64748b;
          line-height: 1.4;
        }

        .change-btn {
          display: flex;
          align-items: center;
          gap: 0.375rem;
          padding: 0.5rem 0.875rem;
          background: #f8fafc;
          border: 1px solid #cbd5e1;
          border-radius: 6px;
          font-size: 0.8125rem;
          font-weight: 500;
          color: #475569;
          cursor: pointer;
          transition: all 0.2s;
          white-space: nowrap;
        }

        .change-btn:hover:not(:disabled) {
          background: #e2e8f0;
          border-color: #94a3b8;
        }

        .change-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .rotated {
          transform: rotate(180deg);
        }

        .error-message {
          padding: 0.625rem 1rem;
          background: #fef3c7;
          color: #92400e;
          font-size: 0.75rem;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          border-top: 1px solid #fde68a;
        }

        .dropdown-overlay {
          position: fixed;
          inset: 0;
          z-index: 9998;
        }

        .profile-dropdown {
          position: absolute;
          top: calc(100% + 0.5rem);
          left: 0;
          right: 0;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
          z-index: 9999;
          overflow: hidden;
        }

        .profile-option {
          padding: 0.875rem 1rem;
          border-left: 4px solid;
          cursor: pointer;
          transition: background 0.15s;
        }

        .profile-option:not(:last-child) {
          border-bottom: 1px solid #f1f5f9;
        }

        .profile-option:hover {
          background: #f8fafc !important;
        }

        .option-content {
          display: flex;
          flex-direction: column;
          gap: 0.375rem;
        }

        .option-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .option-name {
          font-weight: 600;
          color: #1e293b;
          font-size: 0.875rem;
        }

        .option-desc {
          margin: 0;
          font-size: 0.8125rem;
          color: #64748b;
          line-height: 1.4;
        }
      `}</style>
    </div>
  );
};

export default ProfileSelector;
