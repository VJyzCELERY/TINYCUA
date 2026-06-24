// Schema types for Block API responses and requests
export interface Block {
  id: string;
  type: 'text' | 'code' | 'heading' | 'image' | 'bullet-list';
  text_content?: string;
  parent_id?: string;
}

export interface BlockCreate extends Omit<Block, 'id'> {
  content?: string; // For text blocks
}

export interface BlockUpdate extends Partial<Omit<Block, 'id'>> {
  title?: string; // For heading blocks
}

export interface BlockResponse extends Omit<Block, 'id'> {
  id: string;
  type: 'text' | 'code' | 'heading' | 'image' | 'bullet-list';
  text_content?: string;
}

// Search response types
export interface SearchResultItem {
  type: 'block' | 'page' | 'property';
  id: string;
  title: string;
  content?: string | null;
  match_field?: string;
}

export interface SearchResponse {
  query: string;
  page: number;
  page_size: number;
  total_results: number;
  total_pages: number;
  results: SearchResultItem[];
}
