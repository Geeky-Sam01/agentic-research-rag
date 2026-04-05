import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, catchError, throwError } from 'rxjs';

export type UploadStatus = 'idle' | 'uploading' | 'done' | 'error';

@Injectable({ providedIn: 'root' })
export class DocumentService {
  sources = signal<string[]>([]);
  uploadStatus = signal<UploadStatus>('idle');
  totalVectors = signal<number>(0);

  private http = inject(HttpClient);
  private readonly BASE_URL = 'http://localhost:8000';

  fetchStats(): void {
    this.http.get<any>(`${this.BASE_URL}/api/documents/stats`).subscribe({
      next: (data) => {
        this.sources.set(data.sources || []);
        this.totalVectors.set(data.vectors || data.totalVectors || 0);
      },
      error: (err) => console.error('Stats fetch failed:', err)
    });
  }

  uploadDocument(file: File): Observable<any> {
    this.uploadStatus.set('uploading');
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post<any>(`${this.BASE_URL}/api/documents/upload`, formData).pipe(
      tap(() => {
        this.uploadStatus.set('done');
        this.fetchStats();
        setTimeout(() => this.uploadStatus.set('idle'), 3000);
      }),
      catchError(err => {
        this.uploadStatus.set('error');
        setTimeout(() => this.uploadStatus.set('idle'), 3000);
        return throwError(() => err);
      })
    );
  }

  clearIndex(): Observable<any> {
    return this.http.delete<any>(`${this.BASE_URL}/api/documents/clear`).pipe(
      tap(() => {
        this.sources.set([]);
        this.totalVectors.set(0);
      })
    );
  }
}
