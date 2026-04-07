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
    return this.streamChat(query);
  }

  async streamChat(query: string) {
    this.closeStream();

    if (!this.historyService.currentSessionId()) {
      await this.historyService.createNewChat();
    }

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
      content: '',
      timestamp: new Date(),
      isStreaming: true,
      statusHistory: []
    };
    this.messages.update((msgs: Message[]) => [...msgs, assistantMsg]);
    this.loading.set(true);

    const initialStatus = 'Thinking...';
    this.status.set(initialStatus);
    this.statusHistory.set([initialStatus]);
    this.updateMessageStatus(assistantId, initialStatus);

    const url = `${this.BASE_URL}/api/chat/query-stream?query=${encodeURIComponent(query)}&model=${this.selectedModel()}`;
    this.eventSource = new EventSource(url);

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Handle tool calls (thinking markers)
        if (data.type === 'toolcall') {
          const statusMsg = this.getToolStatusMessage(data.tool, data.input);
          this.status.set(statusMsg);
          this.statusHistory.update(prev => [...prev, statusMsg]);
          this.updateMessageStatus(assistantId, statusMsg);
          return;
        }

        // Handle sources metadata
        if (data.type === 'sources' && data.sources) {
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
          
          const msg = `Retrieved ${data.sources.length} relevant sections`;
          this.status.set(msg);
          this.statusHistory.update((prev: string[]) => [...prev, msg]);
          this.updateMessageStatus(assistantId, msg);
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
          let errorMsg = data.error;
          // Exact request: Handle 429 - provider rate limits
          if (typeof errorMsg === 'string' && errorMsg.includes('429')) {
             errorMsg = 'Oops tokens exhausted';
          }
          
          this.messages.update((msgs: Message[]) => msgs.map((m: Message) =>
            m.id === assistantId
              ? { ...m, content: m.content || `⚠️ ${errorMsg}` }
              : m
          ));
          this.finishStream(assistantId);
          return;
        }

        // Append streamed content
        if (data.content) {
          if (data.content.includes('⚠️') || data.content.startsWith('ERROR:')) {
             this.docService.showToast(data.content.replace('ERROR:', '').split('\n')[0]);
          }

          // Once content starts, clear status
          this.status.set(null);
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

    if (!this.historyService.currentSessionId()) {
      await this.historyService.createNewChat();
    }

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
      content: '',
      timestamp: new Date(),
      isStreaming: true,
      statusHistory: []
    };
    this.messages.update((msgs: Message[]) => [...msgs, assistantMsg]);
    this.loading.set(true);
    this.status.set('Structuring output...');

    const payload = {
      query: query,
      stream: false
    };

    this.http.post<any>(`${this.BASE_URL}/api/chat/query-structured`, payload).subscribe({
      next: (data) => {
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
    this.historyService.updateCurrentSession(this.messages(), this.chunks());
  }

  private updateMessageStatus(id: string, status: string) {
    this.messages.update(msgs => msgs.map(m => 
      m.id === id ? { ...m, statusHistory: [...(m.statusHistory || []), status] } : m
    ));
  }

  private closeStream(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  private getToolStatusMessage(tool: string, input: any): string {
    // Exact request: "using tool {tool}..."
    return `using tool ${tool}...`;
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
