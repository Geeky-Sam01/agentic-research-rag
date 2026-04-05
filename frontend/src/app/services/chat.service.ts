import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Message, Chunk, Source } from '../models/chat.models';
import { DocumentService } from './document.service';
import { ChatHistoryService } from './chat-history.service';

@Injectable({ providedIn: 'root' })
export class ChatService {
  messages = signal<Message[]>([]);
  loading = signal<boolean>(false);
  chunks = signal<Chunk[]>([]);
  selectedChunkId = signal<string | null>(null);
  status = signal<string | null>(null);
  statusHistory = signal<string[]>([]);
  selectedModel = signal<string>('openrouter/free');

  private http = inject(HttpClient);
  private docService = inject(DocumentService);
  private historyService = inject(ChatHistoryService);
  private eventSource: EventSource | null = null;
  private readonly BASE_URL = 'http://localhost:8000';

  async sendQuery(query: string) {
    // Retain existing streaming logic as default generic entry point
    return this.streamChat(query);
  }

  async streamChat(query: string) {
    this.closeStream();

    // Ensure we have a session
    if (!this.historyService.currentSessionId()) {
      await this.historyService.createNewChat();
    }

    // Push user message
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
      timestamp: new Date()
    };
    this.messages.update((msgs: Message[]) => [...msgs, userMsg]);

    // Create empty assistant message
    const assistantId = crypto.randomUUID();
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true
    };
    this.messages.update((msgs: Message[]) => [...msgs, assistantMsg]);
    this.loading.set(true);

    if (this.docService.currentSources().length > 0) {
      this.status.set('Searching documents...');
      this.statusHistory.set(['Searching documents...']);
    }

    // Open SSE stream avec model selection
    const url = `${this.BASE_URL}/api/chat/query-stream?query=${encodeURIComponent(query)}&model=${this.selectedModel()}`;
    this.eventSource = new EventSource(url);

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Handle sources metadata (new backend format)
        if (data.type === 'sources' && data.sources) {
          const chunks: Chunk[] = data.sources.map((s: Source, i: number) => ({
            id: `chunk-${i}-${Date.now()}`,
            sourceId: s.source,
            text: s.text,
            similarity: s.similarity
          }));
          this.chunks.set(chunks);

          // Build citation objects and attach to the assistant message
          const citations = data.sources.map((s: Source, i: number) => ({
            id: `cite-${i}-${Date.now()}`,
            chunkId: `chunk-${i}-${Date.now()}`,
            label: s.source
          }));
          this.messages.update((msgs: Message[]) => msgs.map((m: Message) =>
            m.id === assistantId ? { ...m, citations } : m
          ));
          
          if (this.docService.currentSources().length > 0) {
            const msg = `Retrieved ${data.sources.length} relevant sections`;
            this.status.set(msg);
            this.statusHistory.update((prev: string[]) => [...prev, msg]);
            
            // Switch to synthesizing after a small delay for readability
            setTimeout(() => {
              if (this.loading()) {
                const msg2 = 'Synthesizing answer...';
                this.status.set(msg2);
                this.statusHistory.update((prev: string[]) => [...prev, msg2]);
              }
            }, 1000);
          }
          return;
        }

        // Handle stream finish
        const isDone = data.content === '[DONE]' || data.type === 'done';
        if (isDone) {
          this.finishStream(assistantId);
          return;
        }

        // Handle error
        if (data.error) {
          this.messages.update((msgs: Message[]) => msgs.map((m: Message) =>
            m.id === assistantId
              ? { ...m, content: m.content || `⚠️ ${data.error}` }
              : m
          ));
          this.finishStream(assistantId);
          return;
        }

        // Append streamed content
        if (data.content) {
          // Detected error or switch event in the content stream
          if (data.content.includes('⚠️') || data.content.startsWith('ERROR:')) {
             this.docService.showToast(data.content.replace('ERROR:', '').split('\n')[0]);
          }

          // Once content starts, clear status
          this.status.set(null);
          // (keep statusHistory for current message display)
          this.messages.update((msgs: Message[]) => msgs.map((m: Message) =>
            m.id === assistantId
              ? { ...m, content: m.content + data.content }
              : m
          ));
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    this.eventSource.onerror = () => {
      if (this.loading()) {
        this.finishStream(assistantId);
      }
    };
  }

  async structuredChat(query: string) {
    this.closeStream();

    // Ensure we have a session
    if (!this.historyService.currentSessionId()) {
      await this.historyService.createNewChat();
    }

    // Push user message
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
      timestamp: new Date()
    };
    this.messages.update((msgs: Message[]) => [...msgs, userMsg]);

    const assistantId = crypto.randomUUID();
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '', // No markdown text for structured mode
      timestamp: new Date(),
      isStreaming: true
    };
    this.messages.update((msgs: Message[]) => [...msgs, assistantMsg]);
    this.loading.set(true);

    if (this.docService.currentSources().length > 0) {
      this.status.set('Searching parameters & extracting structures...');
      this.statusHistory.set(['Searching documents...', 'Structuring output...']);
    }

    const payload = {
      query: query,
      stream: false
    };

    this.http.post<any>(`${this.BASE_URL}/api/chat/query-structured`, payload).subscribe({
      next: (data) => {
        // Handle sources
        if (data.sources) {
          const chunks: Chunk[] = data.sources.map((s: Source, i: number) => ({
             id: `chunk-${i}-${Date.now()}`,
             sourceId: s.source,
             text: s.text,
             similarity: s.similarity
          }));
          this.chunks.set(chunks);
          
          const citations = data.sources.map((s: Source, i: number) => ({
             id: `cite-${i}-${Date.now()}`,
             chunkId: `chunk-${i}-${Date.now()}`,
             label: s.source
          }));
          
          this.messages.update((msgs: Message[]) => msgs.map((m: Message) =>
             m.id === assistantId ? { ...m, citations } : m
          ));
        }

        // Attach structured payload
        if (data.structuredPayload) {
          this.messages.update((msgs: Message[]) => msgs.map((m: Message) =>
             m.id === assistantId ? { ...m, structuredPayload: data.structuredPayload } : m
          ));
        }

        this.finishStream(assistantId);
      },
      error: (err) => {
        this.messages.update((msgs: Message[]) => msgs.map((m: Message) =>
             m.id === assistantId ? { ...m, content: `⚠️ Error fetching structured response: ${err.message}` } : m
        ));
        this.finishStream(assistantId);
      }
    });
  }

  private finishStream(assistantId: string): void {
    this.closeStream();
    this.loading.set(false);
    this.status.set(null);
    this.statusHistory.set([]);
    this.messages.update((msgs: Message[]) => msgs.map((m: Message) =>
      m.id === assistantId ? { ...m, isStreaming: false } : m
    ));

    // Persist to history
    this.historyService.updateCurrentSession(this.messages(), this.chunks());
  }

  private closeStream(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  setSelectedChunk(id: string | null): void {
    this.selectedChunkId.set(id);
  }

  clearMessages(): void {
    this.closeStream();
    this.messages.set([]);
    this.chunks.set([]);
    this.selectedChunkId.set(null);
    this.loading.set(false);
    this.statusHistory.set([]);
    this.historyService.currentSessionId.set(null);
  }

  async loadSession(id: string) {
    const session = await this.historyService.getSession(id);
    if (session) {
      this.closeStream();
      this.messages.set(session.messages || []);
      this.chunks.set(session.chunks || []);
      this.selectedChunkId.set(null);
      this.loading.set(false);
      this.historyService.currentSessionId.set(id);
    }
  }
}
