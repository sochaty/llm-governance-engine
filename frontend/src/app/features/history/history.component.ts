import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { environment } from '@env/environment';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-history',
  imports: [CommonModule, FormsModule],
  templateUrl: './history.component.html',
  styleUrl: './history.component.scss',
})
export class HistoryComponent implements OnInit{
  private http = inject(HttpClient);
  
  allHistory = signal<any[]>([]);
  filteredHistory = signal<any[]>([]);
  searchTerm = '';
  
  // Pagination
  currentPage = 1;
  pageSize = 10;
  ngOnInit(): void {
    this.loadHistory();
  }

  loadHistory() {
    this.http.get<any[]>(`${environment.apiUrl}/benchmark/history`).subscribe(data => {
      this.allHistory.set(data);
      this.applyFilter();
    });
  }

  applyFilter() {
    const term = this.searchTerm.toLowerCase();
    const filtered = this.allHistory().filter(item => 
      item.prompt.toLowerCase().includes(term) || 
      item.provider.toLowerCase().includes(term) ||
      item.model_name.toLowerCase().includes(term)
    );
    this.filteredHistory.set(filtered);
    this.currentPage = 1; // Reset to first page on search
  }

  get paginatedData() {
    const start = (this.currentPage - 1) * this.pageSize;
    return this.filteredHistory().slice(start, start + this.pageSize);
  }

  get totalPages() {
    return Math.ceil(this.filteredHistory().length / this.pageSize);
  }

  exportToPDF(record: any) {
    console.log('Exporting record:', record.id);
    // We will implement the jsPDF logic here in the next step!
  }

}
