import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HistoryComponent } from './history.component';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { environment } from '@env/environment.prod';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

import { getTestBed } from '@angular/core/testing';
import { BrowserTestingModule, platformBrowserTesting } from '@angular/platform-browser/testing';

// Manual init if global setup fails
try {
  getTestBed().initTestEnvironment(BrowserTestingModule, platformBrowserTesting());
} catch (e) {}

describe('HistoryComponent', () => {
  let component: HistoryComponent;
  let fixture: ComponentFixture<HistoryComponent>;
  let httpMock: HttpTestingController;

  const mockHistoryData = [
    { id: 1, prompt: 'Explain Quantum', provider: 'cloud', model_name: 'gpt-4o', latency_ms: 500 },
    { id: 2, prompt: 'Local Test', provider: 'local', model_name: 'llama3', latency_ms: 100 }
  ];

  beforeEach(async () => {
  await TestBed.configureTestingModule({
    imports: [HistoryComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting()
    ]
  }).compileComponents(); // <--- CRITICAL: Wait for templates to load

    fixture = TestBed.createComponent(HistoryComponent);
    component = fixture.componentInstance;
    // Assign httpMock AFTER TestBed is fully initialized
  httpMock = TestBed.inject(HttpTestingController);
  
  // Note: We do NOT call fixture.detectChanges() here anymore 
  // because we want each 'it' block to handle its own HTTP flushing.
  });

  afterEach(() => {
  // Check if httpMock exists before calling verify to prevent the crash
  if (httpMock) {
    httpMock.verify();
  }
});

  it('should load history and set signals', () => {
    fixture.detectChanges();
    const req = httpMock.expectOne(`${environment.apiUrl}/benchmark/history`);
    req.flush(mockHistoryData);

    expect(component.allHistory().length).toBe(2);
  });

  it('should filter results case-insensitively', () => {
    fixture.detectChanges();
    httpMock.expectOne(`${environment.apiUrl}/benchmark/history`).flush(mockHistoryData);

    component.searchTerm = 'QUANTUM';
    component.applyFilter();

    expect(component.filteredHistory().length).toBe(1);
    expect(component.filteredHistory()[0].prompt).toBe('Explain Quantum');
  });

  it('should disable pagination buttons correctly', () => {
    fixture.detectChanges();
    httpMock.expectOne(`${environment.apiUrl}/benchmark/history`).flush(mockHistoryData);

    const compiled = fixture.nativeElement as HTMLElement;
    const prevBtn = compiled.querySelector('.nav-btns button:first-child') as HTMLButtonElement;
    
    // Vitest/Jest uses .toBe(true)
    expect(prevBtn.disabled).toBe(true);
  });

  it('should call exportToPDF and log to console', () => {
    // Vitest uses vi.spyOn
    const logSpy = vi.spyOn(console, 'log');
    
    fixture.detectChanges();
    httpMock.expectOne(`${environment.apiUrl}/benchmark/history`).flush(mockHistoryData);

    component.exportToPDF(mockHistoryData[0]);
    expect(logSpy).toHaveBeenCalledWith('Exporting record:', 1);
  });
});