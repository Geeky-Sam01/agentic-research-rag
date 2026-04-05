export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  citations?: Citation[];
  timestamp: Date;
  isStreaming?: boolean;
  structuredPayload?: StructuredResponse | null;
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

export type StructuredType = 'table' | 'cards' | 'summary' | 'mixed';

export interface TableResponse {
  type: 'table';
  title: string;
  headers: string[];
  rows: string[][];
}

export interface CardItem {
  heading: string;
  body: string;
  tag: string;
}

export interface CardsResponse {
  type: 'cards';
  title: string;
  cards: CardItem[];
}

export interface SummaryCard {
  type: 'summary';
  headline: string;
  key_points: string[];
  conclusion: string;
}

export interface MixedBlock {
  block_type: string;
  content: any;
}

export interface MixedResponse {
  type: 'mixed';
  blocks: MixedBlock[];
}

export type StructuredResponse = TableResponse | CardsResponse | SummaryCard | MixedResponse;
