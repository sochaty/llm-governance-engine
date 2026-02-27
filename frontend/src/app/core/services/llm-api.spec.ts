import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { describe, it, expect, beforeEach } from 'vitest'; // Explicitly use Vitest globals

import { LlmApi } from './llm-api';
import { getTestBed } from '@angular/core/testing';
import { BrowserTestingModule, platformBrowserTesting } from '@angular/platform-browser/testing';

// Manual init if global setup fails
try {
  getTestBed().initTestEnvironment(BrowserTestingModule, platformBrowserTesting());
} catch (e) {}

describe('LlmApi', () => {
  let service: LlmApi;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      providers: [
        LlmApi,
        provideHttpClient(),
        provideHttpClientTesting(), // Mocks the actual backend calls
      ],
    });
    service = TestBed.inject(LlmApi);
  });

  // beforeEach(async () => {
  //     await TestBed.configureTestingModule({
  //       imports: [DashboardComponent],
  //       providers: [
  //         LlmService,
  //         provideHttpClient(),        // Required if LlmService is injected
  //         provideHttpClientTesting() // Prevents real API calls
  //       ]
  //     }).compileComponents(); // Resolves the .html and .scss files

  
  it('should be created', () => {
    expect(service).toBeTruthy();
  });
  
});