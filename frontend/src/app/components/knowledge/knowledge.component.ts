import { Component, inject, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DocumentService } from '../../services/document.service';
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TooltipModule } from 'primeng/tooltip';

@Component({
  selector: 'app-knowledge',
  standalone: true,
  imports: [CommonModule, TableModule, ButtonModule, ProgressSpinnerModule, TooltipModule],
  templateUrl: './knowledge.component.html',
  styleUrl: './knowledge.component.css'
})
export class KnowledgeComponent implements OnInit {
  private documentService = inject(DocumentService);
  
  ngOnInit(): void {
    // Restore state from backend on load/refresh
    this.documentService.fetchStats();
  }
  
  // Use DocumentService's signals
  public sources = this.documentService.currentSources;
  public status = this.documentService.indexingState;

  // Simulate metadata for now (or get from backend in future)
  public fileList = computed(() => {
    return this.sources().map(name => ({
      name,
      uploadedAt: new Date().toLocaleString(), // Placeholder time
      type: 'PDF'
    }));
  });

  onFileSelected(event: any) {
    const file = event.target.files[0];
    if (file) {
      this.documentService.uploadDocument(file).subscribe({
        next: () => {
          this.documentService.showToast(`Successfully indexed ${file.name}`);
        },
        error: (err) => {
          this.documentService.showToast(`Failed to upload ${file.name}`);
          console.error(err);
        }
      });
    }
  }

  clearKnowledge() {
    if (confirm('Clear the entire knowledge base? This action cannot be undone.')) {
      this.documentService.clearIndex().subscribe();
    }
  }
}
