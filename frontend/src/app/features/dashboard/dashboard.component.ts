import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LlmService } from '../../core/services/llm.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {
  public llmService = inject(LlmService);

  userPrompt = signal('');
  cloudResponse = signal('');
  localResponse = signal('');
  
  // Track latency for the ROI metric
  cloudTime = signal(0);
  localTime = signal(0);

  async runBenchmark() {
    const prompt = this.userPrompt();
    if (!prompt) return;

    // Reset responses
    this.cloudResponse.set('');
    this.localResponse.set('');

    // Run both streams simultaneously
    await Promise.all([
      this.consumeStream(prompt, 'cloud', this.cloudResponse, this.cloudTime),
      this.consumeStream(prompt, 'local', this.localResponse, this.localTime)
    ]);
  }

  private async consumeStream(prompt: string, provider: 'cloud' | 'local', targetSignal: any, timeSignal: any) {
    const start = performance.now();
    const stream = this.llmService.getLlmStream(prompt, provider);
    
    for await (const token of stream) {
      targetSignal.update((val: string) => val + token);
    }
    timeSignal.set(Math.round(performance.now() - start));
  }

}
