import { TestBed } from '@angular/core/testing';

import { LlmApi } from './llm-api';

describe('LlmApi', () => {
  let service: LlmApi;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(LlmApi);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
