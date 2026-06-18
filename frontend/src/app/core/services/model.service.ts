import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '@env/environment';
import { firstValueFrom } from 'rxjs';

export interface OllamaModel {
  name: string;
  size_gb: number;
  modified_at?: string;
}

export interface CatalogModel {
  name: string;
  display_name: string;
  size: string;
  description: string;
  tags: string[];
}

export interface CloudModel {
  id: string;
  name: string;
  context: string;
  cost_per_1m_output: number | null;
}

export interface CloudProvider {
  id: string;
  name: string;
  icon: string;
  key_env: string;
  key_configured: boolean;
  models: CloudModel[];
}

export interface PullProgress {
  status: string;
  percent: number;
  size_downloaded: number;
  size_total: number;
  error?: string;
}

@Injectable({ providedIn: 'root' })
export class ModelService {
  private base = `${environment.apiUrl}/v1/models`;

  cloudProviders = signal<CloudProvider[]>([]);
  installedModels = signal<OllamaModel[]>([]);
  catalogModels = signal<CatalogModel[]>([]);
  pullProgress = signal<PullProgress | null>(null);
  pulling = signal<string | null>(null); // model name being pulled

  constructor(private http: HttpClient) {}

  async loadCloudProviders(): Promise<void> {
    const res = await firstValueFrom(this.http.get<{ providers: CloudProvider[] }>(`${this.base}/cloud`));
    this.cloudProviders.set(res.providers);
  }

  async loadInstalledModels(): Promise<void> {
    try {
      const res = await firstValueFrom(this.http.get<{ models: OllamaModel[] }>(`${this.base}/local`));
      this.installedModels.set(res.models);
    } catch {
      this.installedModels.set([]);
    }
  }

  async loadCatalog(): Promise<void> {
    const res = await firstValueFrom(this.http.get<{ models: CatalogModel[] }>(`${this.base}/local/catalog`));
    this.catalogModels.set(res.models);
  }

  async pullModel(modelName: string): Promise<void> {
    this.pulling.set(modelName);
    this.pullProgress.set({ status: 'starting', percent: 0, size_downloaded: 0, size_total: 0 });

    try {
      const response = await fetch(
        `${this.base}/local/pull?model_name=${encodeURIComponent(modelName)}`,
        { method: 'POST' }
      );

      if (!response.ok || !response.body) {
        throw new Error(`Pull failed: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event: PullProgress = JSON.parse(line.slice(6));
            this.pullProgress.set(event);
            if (event.status === 'done' || event.status === 'success') break;
            if (event.status === 'error') throw new Error(event.error);
          } catch {
            // skip malformed lines
          }
        }
      }

      await this.loadInstalledModels();
    } finally {
      this.pulling.set(null);
    }
  }

  async deleteModel(modelName: string): Promise<void> {
    await firstValueFrom(
      this.http.delete(`${this.base}/local/${encodeURIComponent(modelName)}`)
    );
    await this.loadInstalledModels();
  }
}
