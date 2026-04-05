import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Message, Chunk, Source } from '../models/chat.models';
import { DocumentService } from './document.service';

@Injectable({ providedIn: 'root' })
export class ChatService {
  messages = signal<Message[]>([]);
  loading = signal<boolean>(false);
  chunks = signal<Chunk[]>([]);
  selectedChunkId = signal<string | null>(null);
  status = signal<string | null>(null);
  statusHistory = signal<string[]>([]);

  private http = inject(HttpClient);
  private docService = inject(DocumentService);
  private eventSource: EventSource | null = null;
  private readonly BASE_URL = 'http://localhost:8000';

  sendQuery(query: string): void {
    this.closeStream();

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

    if (this.docService.sources().length > 0) {
      this.status.set('Searching documents...');
      this.statusHistory.set(['Searching documents...']);
    }

    // Open SSE stream
    const url = `${this.BASE_URL}/api/chat/query-stream?query=${encodeURIComponent(query)}`;
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
          
          if (this.docService.sources().length > 0) {
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

  private finishStream(assistantId: string): void {
    this.closeStream();
    this.loading.set(false);
    this.status.set(null);
    this.statusHistory.set([]);
    this.messages.update((msgs: Message[]) => msgs.map((m: Message) =>
      m.id === assistantId ? { ...m, isStreaming: false } : m
    ));
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
  }
}
