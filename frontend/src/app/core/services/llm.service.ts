import { Injectable, signal } from '@angular/core';
import { environment } from '@env/environment';

export interface GovernanceViolation {
  rule_id: string;
  rule_name: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  provider: string;
}

export class GovernanceBlockedError extends Error {
  constructor(public violation: GovernanceViolation) {
    super(`Governance policy violated: ${violation.rule_name}`);
  }
}

@Injectable({
  providedIn: 'root',
})
export class LlmService {
  isStreaming = signal<boolean>(false);

  async *getLlmStream(
    prompt: string,
    provider: 'cloud' | 'local',
    providerType?: string,
    modelId?: string,
  ) {
    this.isStreaming.set(true);

    try {
      let url = `${environment.apiUrl}/benchmark/stream?prompt=${encodeURIComponent(prompt)}&provider=${provider}`;
      if (providerType) url += `&provider_type=${encodeURIComponent(providerType)}`;
      if (modelId) url += `&model_id=${encodeURIComponent(modelId)}`;
      const response = await fetch(url);

      if (response.status === 403) {
        const body = await response.json();
        const detail = body?.detail ?? {};
        throw new GovernanceBlockedError({
          rule_id: detail.rule_id ?? 'unknown',
          rule_name: detail.rule_name ?? 'Policy Violation',
          severity: detail.severity ?? 'high',
          message: detail.message ?? 'Request blocked by governance policy.',
          provider,
        });
      }

      if (!response.ok) {
        throw new Error(`Backend error ${response.status}`);
      }

      if (!response.body) throw new Error('No readable stream available');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        yield decoder.decode(value, { stream: true });
      }
    } finally {
      this.isStreaming.set(false);
    }
  }
}
