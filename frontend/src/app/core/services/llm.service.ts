import { Injectable, signal } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class LlmService {
  private baseUrl = 'http://localhost:8000';

  // Signal to track connection status
  isStreaming = signal<boolean>(false);

  async *getLlmStream(prompt: string, provider: 'cloud' | 'local') {
    this.isStreaming.set(true);
    
    try {
      const response = await fetch(`${this.baseUrl}/benchmark/stream?prompt=${encodeURIComponent(prompt)}&provider=${provider}`);
      
      if (!response.body) throw new Error('No readable stream available');
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        yield decoder.decode(value, { stream: true });
      }
    } catch (error) {
      console.error('Streaming error:', error);
      yield '⚠️ Error connecting to the LLM backend.';
    } finally {
      this.isStreaming.set(false);
    }
  }
}
