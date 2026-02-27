import { TestBed } from '@angular/core/testing';

import { LlmService } from './llm.service';
import { getTestBed } from '@angular/core/testing';
import { BrowserTestingModule, platformBrowserTesting } from '@angular/platform-browser/testing';

// Manual init if global setup fails
try {
  getTestBed().initTestEnvironment(BrowserTestingModule, platformBrowserTesting());
} catch (e) {}

describe('LlmService', () => {
  let service: LlmService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(LlmService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
