export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  citations?: Citation[];
  timestamp: Date;
  isStreaming?: boolean;
}

export interface Source {
  text: string;
  source: string;
  similarity: string;
}

export interface Chunk {
  id: string;
  sourceId: string;
  text: string;
  similarity: string;
}

export interface Citation {
  id: string;
  chunkId: string;
  label: string;
}
