/**
 * Hook for AGENTS.md Coordinator API Integration
 * Provides methods to interact with backend /api/agents endpoints
 */

import { useState, useCallback } from 'react';

export interface PlanStep {
  tool: string;
  input: Record<string, any>;
  reason?: string;
  metadata?: Record<string, any>;
}

export interface ExecutePlanRequest {
  plan_id: string;
  goal: string;
  steps: PlanStep[];
  profile: string;
  request_id: string;
  memory_scope?: string;
}

export interface ExecutePlanResponse {
  status: string;
  result: any;
  error?: string;
  trace: any[];
  signals: {
    success_rate: number;
    error_rate: number;
    latency: {
      p50: number;
      p95: number;
      p99: number;
      mean: number;
    };
    total_events: number;
  };
  budget: {
    total: {
      used: number;
      limit: number;
      percentage: number;
    };
    by_domain?: Record<string, any>;
    by_tool?: Record<string, any>;
  };
  trace_id: string;
}

export interface BudgetInfo {
  profile: string;
  total_calls: number;
  used_calls: number;
  remaining_calls: number;
  utilization: number;
  warning: boolean;
  by_domain: Record<string, any>;
  by_tool: Record<string, any>;
}

const API_BASE = 'http://localhost:8000';

export function useAGENTSCoordinator() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const executePlan = useCallback(async (request: ExecutePlanRequest): Promise<ExecutePlanResponse> => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/agents/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const approve = useCallback(async (approvalId: string, approved: boolean, reason?: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/agents/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approval_id: approvalId,
          approved,
          reason,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const getBudgetInfo = useCallback(async (profile: string): Promise<BudgetInfo> => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/agents/budget/${profile}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const getTrace = useCallback(async (traceId: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/agents/trace/${traceId}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const healthCheck = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/agents/health`);
      if (!response.ok) return false;
      const data = await response.json();
      return data.status === 'healthy';
    } catch {
      return false;
    }
  }, []);

  return {
    executePlan,
    approve,
    getBudgetInfo,
    getTrace,
    healthCheck,
    loading,
    error,
  };
}
