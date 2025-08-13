import { InterventionEvent, TraceEvent, TraceRow, SystemStatus } from './types';

class ApiClient {
  private baseUrl: string;
  private brainUrl: string;

  constructor() {
    this.baseUrl = '/api';
    this.brainUrl = '/brain';
  }

  async fetchJson<T>(url: string): Promise<T> {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  }

  // Brain Server endpoints
  async getInterventionHistory(): Promise<InterventionEvent[]> {
    return this.fetchJson<InterventionEvent[]>(`${this.brainUrl}/history`);
  }

  // Observability Server endpoints
  async getSystemStatus(): Promise<SystemStatus> {
    return this.fetchJson<SystemStatus>(`${this.baseUrl}/status`);
  }

  async getDashboardData(): Promise<{
    total: number;
    trace_count: number;
    traces: TraceRow[];
    insights?: string;
  }> {
    return this.fetchJson<{
      total: number;
      trace_count: number;
      traces: TraceRow[];
      insights?: string;
    }>(`${this.baseUrl}/dashboard`);
  }

  async getTraceDetails(traceId: string): Promise<TraceEvent[]> {
    const response = await this.fetchJson<{
      trace_id: string;
      count: number;
      events: TraceEvent[];
    }>(`${this.baseUrl}/trace/${traceId}`);
    return response.events;
  }

  async getRecentErrors(): Promise<Array<{
    timestamp: string;
    trace_id: string;
    name: string;
    error_type?: string;
    error_message?: string;
  }>> {
    const response = await this.fetchJson<{
      errors: Array<{
        timestamp: string;
        trace_id: string;
        name: string;
        error_type?: string;
        error_message?: string;
      }>;
    }>(`${this.baseUrl}/errors`);
    return response.errors;
  }

  async getAgentGraph(): Promise<{
    nodes: Array<{ id: string; label: string; type: string }>;
    edges: Array<{ source: string; target: string; label: string }>;
    description: string;
  }> {
    return this.fetchJson(`${this.baseUrl}/agent-graph`);
  }
}

export const apiClient = new ApiClient();
