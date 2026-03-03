import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { environment } from '@env/environment';
import { CommonModule } from '@angular/common';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

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
    const doc = new jsPDF();
  const timestamp = new Date(record.created_at).toLocaleString();

  // 1. Header
  doc.setFontSize(20);
  doc.setTextColor(56, 189, 248); // Your theme blue (#38bdf8)
  doc.text('LLM Audit Report', 14, 22);
  
  doc.setFontSize(10);
  doc.setTextColor(100);
  doc.text(`Report Generated: ${new Date().toLocaleString()}`, 14, 30);
  doc.text(`Transaction ID: ${record.id}`, 14, 35);

  // 2. Metadata Table
  autoTable(doc, {
    startY: 45,
    head: [['Metric', 'Value']],
    body: [
      ['Timestamp', timestamp],
      ['Provider', record.provider.toUpperCase()],
      ['Model', record.model_name],
      ['Latency', `${record.latency_ms}ms`],
      ['Cost', `$${record.estimated_cost?.toFixed(4) || '0.0000'}`],
      ['PII Detected', record.pii_detected ? '⚠️ YES' : 'SAFE'],
      ['Safety Score', `${(record.safety_score ?? 1.0) * 100}%`],
    ],
    theme: 'striped',
    headStyles: { fillColor: [30, 41, 59] } // Your card color (#1e293b)
  });

  // 3. Prompt Section
  const finalY = (doc as any).lastAutoTable.finalY + 15;
  doc.setFontSize(14);
  doc.setTextColor(30, 41, 59);
  doc.text('Prompt Context:', 14, finalY);
  
  doc.setFontSize(10);
  doc.setTextColor(50);
  const splitPrompt = doc.splitTextToSize(record.prompt, 180);
  doc.text(splitPrompt, 14, finalY + 7);

  // 4. Response Section
  const responseY = finalY + (splitPrompt.length * 5) + 15;
  doc.setFontSize(14);
  doc.text('Model Response:', 14, responseY);
  
  doc.setFontSize(10);
  const splitResponse = doc.splitTextToSize(record.response_preview, 180);
  doc.text(splitResponse, 14, responseY + 7);

  // 5. Save the PDF
  doc.save(`audit_report_${record.id}.pdf`);
  }

}
