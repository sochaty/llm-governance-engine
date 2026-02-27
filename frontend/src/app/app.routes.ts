import { Routes } from '@angular/router';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { HistoryComponent } from './features/history/history.component';

export const routes: Routes = [
    // {
    //     path: '',
    //     component: DashboardComponent,
    //     title: 'LLM Governance Engine - Dashboard'
    // },
    // {
    //     path: '**',
    //     redirectTo: ''
    // }
    { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'dashboard', component: DashboardComponent },
  { path: 'history', component: HistoryComponent },
  { path: '**', redirectTo: 'dashboard' }
];