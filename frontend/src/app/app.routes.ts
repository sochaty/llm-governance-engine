import { Routes } from '@angular/router';
import { DashboardComponent } from './features/dashboard/dashboard.component';

export const routes: Routes = [
    {
        path: '',
        component: DashboardComponent,
        title: 'LLM Governance Engine - Dashboard'
    },
    {
        path: '**',
        redirectTo: ''
    }
];