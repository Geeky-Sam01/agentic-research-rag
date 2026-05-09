import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { Message, Chunk } from '../models/chat.models';
import { environment } from '../../environments/environment';

export interface ChatSession {
  id: string;
  title: string;
  timestamp: number;
  messages?: Message[];
  chunks?: Chunk[];
}

@Injectable({ providedIn: 'root' })
export class ChatHistoryService {
  private http = inject(HttpClient);
  private readonly BASE_URL = environment.apiUrl;

  sessions = signal<ChatSession[]>([]);
  currentSessionId = signal<string | null>(null);

  groupedSessions = computed(() => {
    const all = this.sessions();
    const groups: { label: string; sessions: ChatSession[] }[] = [];
    
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterday = today - 24 * 60 * 60 * 1000;
    const sevenDaysAgo = today - 7 * 24 * 60 * 60 * 1000;

    const sections: { [key: string]: ChatSession[] } = {};

    all.forEach(session => {
      const date = new Date(session.timestamp);
      const sessionDay = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
      
      let label = '';
      if (sessionDay === today) {
        label = 'Today';
      } else if (sessionDay === yesterday) {
        label = 'Yesterday';
      } else if (sessionDay >= sevenDaysAgo) {
        label = 'Previous 7 Days';
      } else if (date.getFullYear() === now.getFullYear()) {
        label = date.toLocaleString('default', { month: 'long' });
      } else {
        label = date.getFullYear().toString();
      }

      if (!sections[label]) sections[label] = [];
      sections[label].push(session);
    });

    // Sort sections or maintain a specific order if needed, but 'all' is already sorted by latest
    // We want to keep the order in which they appear in 'all'
    const seenLabels = new Set<string>();
    all.forEach(session => {
      const date = new Date(session.timestamp);
      const sessionDay = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
      let label = '';
      if (sessionDay === today) {
        label = 'Today';
      } else if (sessionDay === yesterday) {
        label = 'Yesterday';
      } else if (sessionDay >= sevenDaysAgo) {
        label = 'Previous 7 Days';
      } else if (date.getFullYear() === now.getFullYear()) {
        label = date.toLocaleString('default', { month: 'long' });
      } else {
        label = date.getFullYear().toString();
      }

      if (!seenLabels.has(label)) {
        groups.push({ label, sessions: sections[label] });
        seenLabels.add(label);
      }
    });

    return groups;
  });

  constructor() {
    this.handleLegacyData();
    this.loadSessions();
  }

  private async handleLegacyData() {
    const legacyCount = await this.countLegacyIndexedDBSessions();
    if (legacyCount > 0) {
      alert('Chat history has moved to the server. Previous conversations are not migrated.');
      await this.clearLegacyIndexedDB();
    }
  }

  private async countLegacyIndexedDBSessions(): Promise<number> {
    return new Promise((resolve) => {
      const request = indexedDB.open('AgenticRagDB', 1);
      request.onsuccess = (event: any) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains('chats')) {
          resolve(0);
          return;
        }
        const tx = db.transaction('chats', 'readonly');
        const store = tx.objectStore('chats');
        const countReq = store.count();
        countReq.onsuccess = () => resolve(countReq.result || 0);
        countReq.onerror = () => resolve(0);
      };
      request.onerror = () => resolve(0);
    });
  }

  private async clearLegacyIndexedDB(): Promise<void> {
    return new Promise((resolve) => {
      const request = indexedDB.deleteDatabase('AgenticRagDB');
      request.onsuccess = () => resolve();
      request.onerror = () => resolve();
    });
  }

  async loadSessions() {
    try {
      const res = await firstValueFrom(this.http.get<{sessions: any[]}>(`${this.BASE_URL}/api/chat/sessions`));
      if (res && res.sessions) {
        const mapped: ChatSession[] = res.sessions.map(s => ({
          id: s.id,
          title: s.title,
          timestamp: new Date(s.updated_at).getTime(),
          messages: [],
          chunks: []
        }));
        // Sort by latest
        mapped.sort((a, b) => b.timestamp - a.timestamp);
        this.sessions.set(mapped);
      }
    } catch (e) {
      console.error("Failed to load sessions", e);
    }
  }

  async getSession(id: string): Promise<ChatSession | null> {
    try {
      const res = await firstValueFrom(this.http.get<{messages: any[]}>(`${this.BASE_URL}/api/chat/sessions/${id}/messages`));
      if (res && res.messages) {
        const session = this.sessions().find(s => s.id === id);
        if (!session) return null;
        
        const messages: Message[] = res.messages.map(m => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: new Date(m.created_at),
          citations: [],
          isStreaming: false,
          statusHistory: []
        }));
        
        return {
          ...session,
          messages,
          chunks: []
        };
      }
      return null;
    } catch (e) {
      console.error("Failed to fetch session", e);
      return null;
    }
  }

  async deleteSession(id: string) {
    try {
      await firstValueFrom(this.http.delete(`${this.BASE_URL}/api/chat/sessions/${id}`));
      if (this.currentSessionId() === id) {
        this.currentSessionId.set(null);
      }
      await this.loadSessions();
    } catch (e) {
      console.error("Failed to delete session", e);
    }
  }

  async clearAllSessions() {
    // Currently backend doesn't support clearAll. We can loop or add endpoint.
    for (const session of this.sessions()) {
      await this.deleteSession(session.id);
    }
    this.currentSessionId.set(null);
    this.sessions.set([]);
  }
}
