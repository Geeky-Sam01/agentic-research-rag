import { Component, inject, OnInit } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { DocumentService } from '../../services/document.service';
import { SourceItemComponent } from '../source-item/source-item.component';
import { ButtonModule } from 'primeng/button';
import { ProgressSpinner } from 'primeng/progressspinner';
import { MessageService } from 'primeng/api';

@Component({
  selector: 'app-left-panel',
  standalone: true,
  imports: [CommonModule, SourceItemComponent, ButtonModule, ProgressSpinner, DecimalPipe],
  templateUrl: './left-panel.component.html',
  styleUrl: './left-panel.component.css'
})
export class LeftPanelComponent implements OnInit {
  docService = inject(DocumentService);
  private messageService = inject(MessageService);

  ngOnInit(): void {
    this.docService.fetchStats();
  }

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.docService.uploadDocument(file).subscribe({
      next: (res) => {
        this.messageService.add({
          severity: 'success',
          summary: 'Uploaded',
          detail: res.message || 'Document indexed successfully',
          life: 4000
        });
      },
      error: (err) => {
        this.messageService.add({
          severity: 'error',
          summary: 'Upload Failed',
          detail: err?.error?.detail || 'Could not upload document',
          life: 5000
        });
      }
    });
    // Reset input so same file can be re-uploaded
    input.value = '';
  }
}
