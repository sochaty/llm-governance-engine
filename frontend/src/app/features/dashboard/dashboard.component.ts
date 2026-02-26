import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LlmService } from '../../core/services/llm.service';
import { HttpClient } from '@angular/common/http';
import { environment } from '@env/environment';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
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
  }

  loadData() {
    // Fetch stats
    this.http.get<any>(`${environment.apiUrl}/benchmark/stats`).subscribe(data => {
      this.stats = { ...this.stats, ...data };
    });
    
    // Fetch history
    this.http.get<any[]>(`${environment.apiUrl}/benchmark/history`).subscribe(data => {
      this.history = data;
    });
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
}