export interface BenchmarkResult {
  id: number;
  prompt: string;
  provider: 'cloud' | 'local';
  model_name: string;
  latency_ms: number;
  token_count?: number | null;
  estimated_cost: number;
  created_at: string;
  response_preview?: string | null;
  pii_detected: boolean;
  safety_score: number;
  // Only set when the request supplied `context` — null otherwise.
  faithfulness_score?: number | null;
  context_utilization?: number | null;
  gpu_mem_usage?: number | null;
  energy_watts?: number | null;
  version_tag?: string | null;
}
