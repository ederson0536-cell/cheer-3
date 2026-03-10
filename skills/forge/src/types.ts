export interface SkillMetric {
  id?: number;
  skillId: string;
  executionMs: number;
  tokensIn: number;
  tokensOut: number;
  success: boolean;
  timestamp: number;
  version: string;
}

export interface AggregatedMetrics {
  skillId: string;
  avgExecutionMs: number;
  avgTokensIn: number;
  avgTokensOut: number;
  totalRuns: number;
  failureRate: number;
  p95ExecutionMs: number;
}

export interface AnalysisResult {
  skillId: string;
  metrics: AggregatedMetrics;
  score: number;          // 0-100, higher = more wasteful
  reasons: string[];
  recommendation: 'optimize' | 'monitor' | 'ok';
}

export interface OptimizationResult {
  skillId: string;
  originalPath: string;
  optimizedPath: string;
  optimizedContent: string;
  changes: string[];
  estimatedSavings: {
    tokens: number;
    timeMs: number;
  };
}

export interface ValidationResult {
  skillId: string;
  version: string;
  passed: boolean;
  originalOutput: string;
  optimizedOutput: string;
  similarityScore: number;
  speedImprovement: number;
  tokenSavings: number;
}

export interface ForgeEvent {
  timestamp: number;
  module: 'profiler' | 'analyzer' | 'optimizer' | 'validator' | 'forge';
  action: string;
  skillId: string;
  details: string;
}
