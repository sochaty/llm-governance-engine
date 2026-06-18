import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ChartConfiguration, ChartData } from 'chart.js';
import { BaseChartDirective } from 'ng2-charts';
import { HttpClient } from '@angular/common/http';
import { environment } from '@env/environment';
import { LlmService, GovernanceBlockedError, GovernanceViolation } from '../../core/services/llm.service';
import { ModelSelectorComponent, CloudSelection, LocalSelection } from '../model-selector/model-selector.component';
import { Chart, registerables } from 'chart.js';
Chart.register(...registerables);

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, BaseChartDirective, ModelSelectorComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  private http = inject(HttpClient);
  public llmService = inject(LlmService);

  stats = {
    total_savings: 0,
    avg_cloud_latency: 0,
    avg_local_latency: 0,
    total_requests: 0,
    avg_cloud_cost: 0
  };

  history: any[] = [];
  userPrompt = signal('');

  cloudResponse = signal('');
  localResponse = signal('');
  cloudTime = signal(0);
  localTime = signal(0);

  // Governance violation state — set when backend returns 403
  cloudViolation = signal<GovernanceViolation | null>(null);
  localViolation = signal<GovernanceViolation | null>(null);

  // Selected model overrides from the model-selector component
  cloudSelection = signal<CloudSelection | null>(null);
  localSelection = signal<LocalSelection | null>(null);

  // Display names for the comparison card headers
  cloudCardLabel = signal('Frontier (Cloud)');
  localCardLabel = signal('Local (Ollama)');

  ngOnInit(): void {
    this.loadData();
    this.radarChartData.datasets[0].data = [80, 70, 90, 60, 50, 80, 70, 90, 60, 50];
    this.radarChartData = { ...this.radarChartData };
  }

  public radarChartOptions: ChartConfiguration['options'] = {
    responsive: true,
    scales: {
      r: {
        angleLines: { color: '#334155' },
        grid: { color: '#334155' },
        pointLabels: { color: '#94a3b8', font: { size: 12 } },
        ticks: { display: false },
        suggestedMin: 0,
        suggestedMax: 100
      }
    },
    plugins: {
      legend: { labels: { color: '#f8fafc' } }
    }
  };

  public radarChartLabels: string[] = [
    'Speed', 'Cost Efficiency', 'Throughput', 'Safety',
    'PII Protection', 'Faithfulness', 'Context Efficiency',
    'GPU Optimization', 'Sustainability', 'Reliability'
  ];

  public radarChartData: ChartData<'radar'> = {
    labels: this.radarChartLabels,
    datasets: [
      {
        data: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        label: 'Frontier (Cloud)',
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56, 189, 248, 0.2)'
      },
      {
        data: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        label: 'Local (Edge)',
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.2)'
      }
    ]
  };

  loadData() {
    this.http.get<any>(`${environment.apiUrl}/benchmark/stats`).subscribe(data => {
      this.stats = { ...this.stats, ...data };
    });
    this.http.get<any[]>(`${environment.apiUrl}/benchmark/history`).subscribe(data => {
      this.history = data;
      this.updateRadarChart();
    });
  }

  async runBenchmark() {
    const prompt = this.userPrompt();
    if (!prompt) return;

    // Clear previous state
    this.cloudResponse.set('');
    this.localResponse.set('');
    this.cloudTime.set(0);
    this.localTime.set(0);
    this.cloudViolation.set(null);
    this.localViolation.set(null);

    const cloudSel = this.cloudSelection();
    const localSel = this.localSelection();

    await Promise.all([
      this.consumeStream(
        prompt, 'cloud', this.cloudResponse, this.cloudTime, this.cloudViolation,
        cloudSel?.provider_type, cloudSel?.model_id,
      ),
      this.consumeStream(
        prompt, 'local', this.localResponse, this.localTime, this.localViolation,
        localSel ? 'ollama' : undefined, localSel?.model_id,
      ),
    ]);

    this.loadData();
  }

  onCloudModelChanged(sel: CloudSelection): void {
    this.cloudSelection.set(sel);
    this.cloudCardLabel.set(`${sel.model_name} (${sel.provider_type})`);
  }

  onLocalModelChanged(sel: LocalSelection): void {
    this.localSelection.set(sel);
    this.localCardLabel.set(`Local: ${sel.model_id}`);
  }

  dismissViolation(provider: 'cloud' | 'local') {
    if (provider === 'cloud') this.cloudViolation.set(null);
    else this.localViolation.set(null);
  }

  severityClass(severity: string): string {
    return {
      critical: 'sev-critical',
      high: 'sev-high',
      medium: 'sev-medium',
      low: 'sev-low',
    }[severity] ?? 'sev-high';
  }

  private async consumeStream(
    prompt: string,
    provider: 'cloud' | 'local',
    targetSignal: any,
    timeSignal: any,
    violationSignal: any,
    providerType?: string,
    modelId?: string,
  ) {
    const start = performance.now();
    try {
      const stream = this.llmService.getLlmStream(prompt, provider, providerType, modelId);
      for await (const token of stream) {
        targetSignal.update((val: string) => val + token);
      }
      timeSignal.set(Math.round(performance.now() - start));
    } catch (error) {
      if (error instanceof GovernanceBlockedError) {
        violationSignal.set(error.violation);
        targetSignal.set('');
      } else {
        console.error(`${provider} stream failed:`, error);
        targetSignal.set(`Error: Failed to connect to ${provider} provider.`);
      }
    }
  }

  private updateRadarChart() {
    if (!this.history || this.history.length === 0) return;

    const cloud = this.history.find(h => h.provider === 'cloud');
    const local = this.history.find(h => h.provider === 'local');

    if (cloud) {
      this.radarChartData.datasets[0].data = [
        this.normalize(cloud.latency_ms, 3000, true),
        this.normalize(cloud.estimated_cost, 0.05, true),
        this.normalize(cloud.token_count || 50, 200),
        (cloud.safety_score ?? 0.98) * 100,
        (cloud.pii_detected ? 20 : 100),
        (cloud.faithfulness_score ?? 0.95) * 100,
        cloud.context_utilization ?? 85,
        90,
        60,
        95
      ];
    }

    if (local) {
      this.radarChartData.datasets[1].data = [
        this.normalize(local.latency_ms, 3000, true),
        100,
        this.normalize(local.token_count || 30, 200),
        (local.safety_score ?? 0.90) * 100,
        100,
        (local.faithfulness_score ?? 0.85) * 100,
        local.context_utilization ?? 30,
        this.normalize(local.gpu_mem_usage || 2000, 8000, true),
        95,
        85
      ];
    }

    this.radarChartData = { ...this.radarChartData };
  }

  private normalize(val: number | undefined, max: number, invert: boolean = false): number {
    const safeVal = val || 0;
    let score = (safeVal / max) * 100;
    if (invert) score = 100 - score;
    const finalScore = Math.max(5, Math.min(100, score));
    return isNaN(finalScore) ? 5 : finalScore;
  }
}
