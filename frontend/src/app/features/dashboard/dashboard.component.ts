import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ChartConfiguration, ChartData, ChartType } from 'chart.js';
import { BaseChartDirective } from 'ng2-charts';
import { HttpClient } from '@angular/common/http';
import { environment } from '@env/environment';
import { LlmService } from '../../core/services/llm.service';
import { Chart, registerables } from 'chart.js';
Chart.register(...registerables);

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, BaseChartDirective],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  private http = inject(HttpClient);
  public llmService = inject(LlmService);

  // 1. Added avg_cloud_cost to satisfy the AOT compiler
  stats = { 
    total_savings: 0, 
    avg_cloud_latency: 0, 
    avg_local_latency: 0, 
    total_requests: 0,
    avg_cloud_cost: 0 
  };
  
  history: any[] = [];
  userPrompt = signal('');
  
  // 2. Response and Timing signals
  cloudResponse = signal('');
  localResponse = signal('');
  cloudTime = signal(0);
  localTime = signal(0);

  ngOnInit(): void {
    this.loadData();
    // Force a test shape
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

    // Fetch stats
    this.http.get<any>(`${environment.apiUrl}/benchmark/stats`).subscribe(data => {
      this.stats = { ...this.stats, ...data };
      console.log('Fetched stats:', this.stats);
    });

    // Fetch history and update radar chart    
    this.http.get<any[]>(`${environment.apiUrl}/benchmark/history`).subscribe(data => {
      this.history = data;
      this.updateRadarChart(); // Update chart whenever history is refreshed
      console.log('Fetched history:', this.history);
    });
    console.log('Initial history load:', this.history);
  }

  async runBenchmark() {
    const prompt = this.userPrompt();
    if (!prompt) return;

    // Reset UI state
    this.cloudResponse.set('');
    this.localResponse.set('');
    this.cloudTime.set(0);
    this.localTime.set(0);

    // Run both streams simultaneously
    await Promise.all([
      this.consumeStream(prompt, 'cloud', this.cloudResponse, this.cloudTime),
      this.consumeStream(prompt, 'local', this.localResponse, this.localTime)
    ]);

    // 3. Refresh the ROI stats after benchmark completes
    this.loadData();
  }

  private async consumeStream(prompt: string, provider: 'cloud' | 'local', targetSignal: any, timeSignal: any) {
    const start = performance.now();
    try {
      const stream = this.llmService.getLlmStream(prompt, provider);
      for await (const token of stream) {
        targetSignal.update((val: string) => val + token);
      }
      timeSignal.set(Math.round(performance.now() - start));
    } catch (error) {
      console.error(`${provider} stream failed:`, error);
      targetSignal.set(`Error: Failed to connect to ${provider} provider.`);
    }
  }

  private updateRadarChart() {
    console.log('History data for chart:', this.history); // Check if history exists
    if (!this.history || this.history.length === 0) return;

    // Get latest entries for each provider
    const cloud = this.history.find(h => h.provider === 'cloud');
    const local = this.history.find(h => h.provider === 'local');
    console.log('Found Cloud:', cloud, 'Found Local:', local);

    if (cloud) {
      this.radarChartData.datasets[0].data = [
      this.normalize(cloud.latency_ms, 3000, true),           // Speed
      this.normalize(cloud.estimated_cost, 0.05, true),      // Cost Efficiency
      this.normalize(cloud.token_count || 50, 200),           // Throughput
      (cloud.safety_score ?? 0.98) * 100,                     // Safety (Fallback 98)
      (cloud.pii_detected ? 20 : 100),                        // PII Protection
      (cloud.faithfulness_score ?? 0.95) * 100,               // Faithfulness
      cloud.context_utilization ?? 85,                        // Context
      90,                                                     // GPU Opt (Cloud is high)
      60,                                                     // Sustainability
      95                                                      // Reliability
    ];
    }

    if (local) {
      this.radarChartData.datasets[1].data = [
      this.normalize(local.latency_ms, 3000, true),
      100,                                                    // Local Cost is always 100% efficient
      this.normalize(local.token_count || 30, 200),
      (local.safety_score ?? 0.90) * 100,
      (local.pii_detected ? 100 : 100),                       // Local is private
      (local.faithfulness_score ?? 0.85) * 100,
      local.context_utilization ?? 30,
      this.normalize(local.gpu_mem_usage || 2000, 8000, true),// GPU Usage
      95,                                                     // Sustainability
      85                                                      // Reliability
    ];
    }
console.log('Final Cloud Dataset:', this.radarChartData.datasets[0].data);
    // Reference update to trigger Angular Change Detection for the chart
    this.radarChartData = { ...this.radarChartData };
  }

  private normalize(val: number | undefined, max: number, invert: boolean = false): number {
    // const safeVal = val || 0;
    // let score = (safeVal / max) * 100;
    // if (invert) score = 100 - score;
    // return Math.max(5, Math.min(100, score)); // Keep min 5 for visual visibility
    const safeVal = val || 0;
    let score = (safeVal / max) * 100;
    if (invert) score = 100 - score;
    const finalScore = Math.max(5, Math.min(100, score));
    return isNaN(finalScore) ? 5 : finalScore; // Safety check
  }
}