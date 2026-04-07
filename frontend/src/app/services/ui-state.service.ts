import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class UiStateService {
  showHistory = signal(true);   // Chat history sidebar — open by default
  showSources = signal(false);  // Knowledge base drawer — closed by default
  showEvidence = signal(false); // Evidence panel — closed by default
  
  // Primary Workspace Mode
  activeWorkspace = signal<'chat' | 'knowledge'>('chat');

  toggleHistory()  { this.showHistory.update(v => !v); }
  toggleSources()  { this.showSources.update(v => !v); }
  toggleEvidence() { this.showEvidence.update(v => !v); }
  openEvidence()   { this.showEvidence.set(true); }
  
  setWorkspace(mode: 'chat' | 'knowledge') {
    this.activeWorkspace.set(mode);
  }
}
