import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '@env/environment';
import { firstValueFrom } from 'rxjs';

export interface SettingEntry {
  key: string;
  label: string;
  section: string;
  provider: string | null;
  sensitive: boolean;
  source: 'db' | 'env' | 'unset';
  is_set: boolean;
  masked_value: string;
}

@Injectable({ providedIn: 'root' })
export class SettingsService {
  private base = `${environment.apiUrl}/v1/settings`;

  settings = signal<SettingEntry[]>([]);
  saving = signal(false);
  saveError = signal<string | null>(null);
  saveSuccess = signal(false);

  constructor(private http: HttpClient) {}

  async load(): Promise<void> {
    const res = await firstValueFrom(
      this.http.get<{ settings: SettingEntry[] }>(this.base)
    );
    this.settings.set(res.settings);
  }

  async save(updates: Record<string, string>): Promise<void> {
    this.saving.set(true);
    this.saveError.set(null);
    this.saveSuccess.set(false);
    try {
      const res = await firstValueFrom(
        this.http.put<{ settings: SettingEntry[] }>(this.base, { settings: updates })
      );
      this.settings.set(res.settings);
      this.saveSuccess.set(true);
      setTimeout(() => this.saveSuccess.set(false), 3000);
    } catch (err: any) {
      this.saveError.set(err?.error?.detail ?? 'Failed to save settings.');
    } finally {
      this.saving.set(false);
    }
  }

  async deleteSetting(key: string): Promise<void> {
    await firstValueFrom(this.http.delete(`${this.base}/${key}`));
    await this.load();
  }
}
