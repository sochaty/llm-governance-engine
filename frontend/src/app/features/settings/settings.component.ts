import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsService, SettingEntry } from '../../core/services/settings.service';

interface FieldState {
  editing: boolean;
  value: string;
  show: boolean;
}

const SECTIONS: { id: string; label: string; icon: string; description: string }[] = [
  { id: 'cloud', label: 'Cloud Provider Keys', icon: '☁️', description: 'API keys for OpenAI, Anthropic, Google and Groq. Stored encrypted in PostgreSQL.' },
  { id: 'local', label: 'Local Model', icon: '⚙️', description: 'Ollama endpoint configuration.' },
  { id: 'models', label: 'Model Defaults', icon: '🤖', description: 'Default model names and timeouts when no model is selected in the UI.' },
  { id: 'governance', label: 'Governance', icon: '🛡️', description: 'Active policy file path.' },
];

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
})
export class SettingsComponent implements OnInit {
  settingsService = inject(SettingsService);

  sections = SECTIONS;
  fieldStates: Record<string, FieldState> = {};
  loading = signal(true);

  async ngOnInit(): Promise<void> {
    await this.settingsService.load();
    this.initFieldStates();
    this.loading.set(false);
  }

  private initFieldStates(): void {
    for (const s of this.settingsService.settings()) {
      this.fieldStates[s.key] = { editing: false, value: '', show: false };
    }
  }

  settingsForSection(section: string): SettingEntry[] {
    return this.settingsService.settings().filter(s => s.section === section);
  }

  startEdit(key: string): void {
    this.fieldStates[key] = { ...this.fieldStates[key], editing: true, value: '' };
  }

  cancelEdit(key: string): void {
    this.fieldStates[key] = { ...this.fieldStates[key], editing: false, value: '' };
  }

  toggleShow(key: string): void {
    this.fieldStates[key].show = !this.fieldStates[key].show;
  }

  async saveField(key: string): Promise<void> {
    const val = this.fieldStates[key].value.trim();
    await this.settingsService.save({ [key]: val });
    this.fieldStates[key] = { editing: false, value: '', show: false };
  }

  async clearField(key: string): Promise<void> {
    if (!confirm(`Remove DB override for ${key}? The environment variable will take effect.`)) return;
    await this.settingsService.deleteSetting(key);
  }

  sourceLabel(s: SettingEntry): string {
    if (s.source === 'db') return 'Saved (DB)';
    if (s.source === 'env') return 'From .env';
    return 'Not set';
  }

  sourceBadgeClass(s: SettingEntry): string {
    if (s.source === 'db') return 'badge-db';
    if (s.source === 'env') return 'badge-env';
    return 'badge-unset';
  }
}
