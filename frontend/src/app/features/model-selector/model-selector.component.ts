import { Component, inject, OnInit, output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ModelService, CatalogModel, CloudProvider, OllamaModel } from '../../core/services/model.service';

export interface CloudSelection {
  provider_type: string;
  model_id: string;
  model_name: string;
}

export interface LocalSelection {
  model_id: string;
}

@Component({
  selector: 'app-model-selector',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './model-selector.component.html',
  styleUrl: './model-selector.component.scss',
})
export class ModelSelectorComponent implements OnInit {
  modelService = inject(ModelService);

  cloudChanged = output<CloudSelection>();
  localChanged = output<LocalSelection>();

  activeCloudProvider = signal<string>('openai');
  selectedCloudModel = signal<string>('gpt-4o');
  selectedLocalModel = signal<string>('');
  showCatalog = signal<boolean>(false);
  catalogFilter = signal<string>('');

  ngOnInit(): void {
    this.modelService.loadCloudProviders();
    this.modelService.loadInstalledModels();
    this.modelService.loadCatalog();
  }

  get currentProvider(): CloudProvider | undefined {
    return this.modelService.cloudProviders().find(p => p.id === this.activeCloudProvider());
  }

  get filteredCatalog(): CatalogModel[] {
    const q = this.catalogFilter().toLowerCase();
    return this.modelService.catalogModels().filter(
      m => !q || m.name.includes(q) || m.display_name.toLowerCase().includes(q) || m.tags.some(t => t.includes(q))
    );
  }

  isInstalled(name: string): boolean {
    return this.modelService.installedModels().some(m => m.name === name || m.name.startsWith(name + ':'));
  }

  selectCloudProvider(id: string): void {
    this.activeCloudProvider.set(id);
    const provider = this.modelService.cloudProviders().find(p => p.id === id);
    if (provider?.models?.length) {
      this.selectCloudModel(id, provider.models[0].id, provider.models[0].name);
    }
  }

  selectCloudModel(providerId: string, modelId: string, modelName: string): void {
    this.selectedCloudModel.set(modelId);
    this.cloudChanged.emit({ provider_type: providerId, model_id: modelId, model_name: modelName });
  }

  selectLocalModel(name: string): void {
    this.selectedLocalModel.set(name);
    this.localChanged.emit({ model_id: name });
  }

  async pullModel(name: string): Promise<void> {
    await this.modelService.pullModel(name);
    this.selectLocalModel(name + ':latest');
  }

  pullProgressLabel(): string {
    const p = this.modelService.pullProgress();
    if (!p) return '';
    if (p.status === 'error') return `Error: ${p.error}`;
    if (p.size_total > 0) return `${p.size_downloaded.toFixed(1)} / ${p.size_total.toFixed(1)} GB (${p.percent}%)`;
    return p.status;
  }
}
