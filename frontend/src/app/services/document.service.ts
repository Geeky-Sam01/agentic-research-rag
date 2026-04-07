import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, catchError, throwError } from 'rxjs';
import { ChatHistoryService } from './chat-history.service';
import { environment } from '../../environments/environment';

export type UploadStatus = 'idle' | 'uploading' | 'done' | 'error';

@Injectable({ providedIn: 'root' })
export class DocumentService {
  public currentSources = signal<string[]>([]);
  public indexingState = signal<UploadStatus>('idle');
  public vectorStats = signal<number>(0);
  public toastMessage = signal<string | null>(null);
  public suggestedQuestions = signal<string[]>([]);

  private http = inject(HttpClient);
  private historyService = inject(ChatHistoryService);
  private readonly BASE_URL = environment.apiUrl;

  showToast(msg: string) {
    this.toastMessage.set(msg);
    setTimeout(() => this.toastMessage.set(null), 5000);
  }

  fetchStats(): void {
    this.http.get<any>(`${this.BASE_URL}/api/documents/stats`).subscribe({
      next: (data) => {
        this.currentSources.set(data.sources || []);
        this.vectorStats.set(data.vectors || data.totalVectors || 0);
      },
      error: (err) => console.error('Stats fetch failed:', err)
    });
  }

  uploadDocument(file: File): Observable<any> {
    this.indexingState.set('uploading');
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post<any>(`${this.BASE_URL}/api/documents/upload`, formData).pipe(
      tap((res) => {
        this.indexingState.set('done');
        this.suggestedQuestions.set(res.suggested_questions || []);
        this.fetchStats();
        setTimeout(() => this.indexingState.set('idle'), 3000);
      }),
      catchError(err => {
        this.indexingState.set('error');
        setTimeout(() => this.indexingState.set('idle'), 3000);
        return throwError(() => err);
      })
    );
  }

  clearIndex(): Observable<any> {
    return this.http.delete<any>(`${this.BASE_URL}/api/documents/clear`).pipe(
      tap(() => {
        this.currentSources.set([]);
        this.vectorStats.set(0);
        this.suggestedQuestions.set([]);
        this.historyService.clearAllSessions();
      })
    );
  }
}
