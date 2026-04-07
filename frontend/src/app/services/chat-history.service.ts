import { Injectable, signal, computed } from '@angular/core';
import { Message, Chunk } from '../models/chat.models';

export interface ChatSession {
  id: string;
  title: string;
  timestamp: number;
  messages: Message[];
  chunks: Chunk[];
}

@Injectable({ providedIn: 'root' })
export class ChatHistoryService {
  private readonly DB_NAME = 'AgenticRagDB';
  private readonly STORE_NAME = 'chats';
  private db: IDBDatabase | null = null;
  private dbReady: Promise<IDBDatabase>;
  private dbResolve!: (db: IDBDatabase) => void;

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
    this.dbReady = new Promise((resolve) => {
      this.dbResolve = resolve;
    });
    this.initDB();
  }

  private async initDB() {
    const request = indexedDB.open(this.DB_NAME, 1);

    request.onupgradeneeded = (event: any) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(this.STORE_NAME)) {
        db.createObjectStore(this.STORE_NAME, { keyPath: 'id' });
      }
    };

    request.onsuccess = (event: any) => {
      this.db = event.target.result;
      this.dbResolve(this.db!);
      this.loadSessions();
    };
  }

  async loadSessions() {
    const db = await this.dbReady;
    const tx = db.transaction(this.STORE_NAME, 'readonly');
    const store = tx.objectStore(this.STORE_NAME);
    const request = store.getAll();

    request.onsuccess = () => {
      const all: ChatSession[] = request.result;
      // Sort by latest
      all.sort((a, b) => b.timestamp - a.timestamp);
      this.sessions.set(all);
    };
  }

  async createNewChat(): Promise<string> {
    const newId = crypto.randomUUID();
    const newSession: ChatSession = {
      id: newId,
      title: 'New Chat',
      timestamp: Date.now(),
      messages: [],
      chunks: []
    };

    await this.saveSession(newSession);
    this.currentSessionId.set(newId);
    return newId;
  }

  async saveSession(session: ChatSession) {
    const db = await this.dbReady;
    const tx = db.transaction(this.STORE_NAME, 'readwrite');
    const store = tx.objectStore(this.STORE_NAME);
    store.put(session);

    tx.oncomplete = () => {
      this.loadSessions();
    };
  }

  async getSession(id: string): Promise<ChatSession | null> {
    const db = await this.dbReady;
    return new Promise((resolve) => {
      const tx = db.transaction(this.STORE_NAME, 'readonly');
      const store = tx.objectStore(this.STORE_NAME);
      const request = store.get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(null);
    });
  }

  async updateCurrentSession(messages: Message[], chunks: Chunk[]) {
    const id = this.currentSessionId();
    if (!id) return;

    const session = await this.getSession(id);
    if (session) {
      session.messages = messages;
      session.chunks = chunks;
      
      // Update title if it's still 'New Chat' and we have at least one user message
      if (session.title === 'New Chat' && messages.length > 0) {
        const userMsg = messages.find(m => m.role === 'user');
        if (userMsg) {
          session.title = userMsg.content.slice(0, 40) + (userMsg.content.length > 40 ? '...' : '');
        }
      }
      
      await this.saveSession(session);
    }
  }

  async deleteSession(id: string) {
    const db = await this.dbReady;
    const tx = db.transaction(this.STORE_NAME, 'readwrite');
    const store = tx.objectStore(this.STORE_NAME);
    store.delete(id);

    tx.oncomplete = () => {
      if (this.currentSessionId() === id) {
        this.currentSessionId.set(null);
      }
      this.loadSessions();
    };
  }

  async clearAllSessions() {
    const db = await this.dbReady;
    const tx = db.transaction(this.STORE_NAME, 'readwrite');
    const store = tx.objectStore(this.STORE_NAME);
    store.clear();

    tx.oncomplete = () => {
      this.currentSessionId.set(null);
      this.sessions.set([]);
    };
  }
}
