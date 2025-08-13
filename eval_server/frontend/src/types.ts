export interface InterventionEvent {
  timestamp: string;
  request: {
    function_name: string;
    url?: string;
  };
  content_preview: string;
  content_length: number;
  decision: string;
  final_output: string;
}

export interface TraceEvent {
  trace_id: string;
  span_id: string;
  parent_span_id?: string;
  event_type: string;
  name: string;
  category?: string;
  status: string;
  timestamp: string;
  server_ts?: string;
  duration_ms?: number;
  args_preview?: string;
  kwargs_preview?: string;
  result_preview?: string;
  error_type?: string;
  error_message?: string;
  metadata?: Record<string, any>;
}

export interface TraceRow {
  trace_id: string;
  span_count: number;
  error_count: number;
  duration_ms: number;
}

export interface DatabaseStatus {
  connected: boolean;
  status: string;
  trace_count: number;
}

export interface SystemStatus {
  ok: boolean;
  database: DatabaseStatus;
  memory: {
    trace_count: number;
  };
  data_source: string;
}
