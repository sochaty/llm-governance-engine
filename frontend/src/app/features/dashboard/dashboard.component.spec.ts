import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DashboardComponent } from './dashboard.component';
import { LlmService } from '../../core/services/llm.service';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { getTestBed } from '@angular/core/testing';
import { BrowserTestingModule, platformBrowserTesting } from '@angular/platform-browser/testing';

// Manual init if global setup fails
try {
  getTestBed().initTestEnvironment(BrowserTestingModule, platformBrowserTesting());
} catch (e) {}

describe('DashboardComponent', () => {
  let component: DashboardComponent;
  let fixture: ComponentFixture<DashboardComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        LlmService,
        provideHttpClient(),        // Required if LlmService is injected
        provideHttpClientTesting() // Prevents real API calls
      ]
    }).compileComponents(); // Resolves the .html and .scss files

    fixture = TestBed.createComponent(DashboardComponent);
    component = fixture.componentInstance;
    
    // We wrap detectChanges in a try-catch or ensure signals are ready
    fixture.detectChanges(); 
  });

  it('should initialize with empty signals', () => {
    // Note: If these are Angular Signals, call them as functions: ()
    expect(component.cloudResponse()).toBe('');
    expect(component.localResponse()).toBe('');
  });
});