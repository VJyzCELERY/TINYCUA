import { useState, useEffect } from 'react';
import './DocumentView.css';
import BlockToolbar from './BlockToolbar';

// Types matching backend API responses
interface Block {
  id: string;
  type: 'text' | 'code' | 'heading' | 'image' | 'bullet-list';
  text_content?: string;
  parent_id?: string;
}

// API configuration - backend URL and paths
const API_BASE = '/api/v1';

export function DocumentView() {
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Auth token for API requests - stored in localStorage
  const authToken = useState<string | null>(() => localStorage.getItem('auth_token'))[0];

  // Fetch blocks from backend API on mount
  useEffect(() => {
    async function fetchBlocks() {
      try {
        setIsLoading(true);
        
        // Include auth token if available
        const headers: HeadersInit = {};
        if (authToken) {
          headers['Authorization'] = `Bearer ${authToken}`;
        }

        const response = await fetch(`${API_BASE}/blocks`, { headers });
        
        if (!response.ok) {
          throw new Error(`Failed to load blocks: ${response.status} ${response.statusText}`);
        }
        
        const data: Block[] = await response.json();
        setBlocks(data);
        setIsLoading(false);
      } catch (err: unknown) {
        const error = err instanceof Error ? err.message : 'Unknown error';
        console.error('Error fetching blocks:', error);
        setError(error);
        setIsLoading(false);
        
        // Set empty state with retry option
        setBlocks([]);
      }
    }
    
    if (authToken) {
      fetchBlocks();
    } else {
      setIsLoading(false);
      setBlocks([]);
    }
  }, [authToken]);

  // Handle block creation via toolbar insertion
  async function handleCreateBlock(type: string, content?: string) {
    try {
      const headers: HeadersInit = {};
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }
      
      const response = await fetch(`${API_BASE}/blocks`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ type, text_content: content })
      });
      
      if (!response.ok) {
        throw new Error(`Failed to create block: ${response.status}`);
      }
      
      const data: Block = await response.json();
      setBlocks(prev => [...prev, data]);
      return data;
    } catch (err) {
      console.error('Error creating block:', err);
      setError(err instanceof Error ? err.message : 'Failed to create block');
      return null;
    }
  }

  // Handle block update via PUT endpoint - not currently used but kept for future features
  async function handleUpdateBlock(blockId: string, updates: { type?: string; text_content?: string }) {
    try {
      const headers: HeadersInit = {};
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }
      
      const response = await fetch(`${API_BASE}/blocks/${blockId}/update`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(updates)
      });
      
      if (!response.ok) {
        throw new Error(`Failed to update block: ${response.status}`);
      }
      
      const data: Block = await response.json();
      setBlocks(prev => prev.map(b => b.id === blockId ? data : b));
      return data;
    } catch (err) {
      console.error('Error updating block:', err);
      setError(err instanceof Error ? err.message : 'Failed to update block');
      return null;
    }
  }

  // Handle block deletion with confirmation
  async function handleDeleteBlock(blockId: string) {
    if (!window.confirm('Are you sure you want to delete this block?')) return;
    
    try {
      const headers: HeadersInit = {};
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }
      
      const response = await fetch(`${API_BASE}/blocks/${blockId}`, { 
        method: 'DELETE',
        headers 
      });
      
      if (!response.ok) {
        throw new Error(`Failed to delete block: ${response.status}`);
      }
      
      setBlocks(prev => prev.filter(b => b.id !== blockId));
    } catch (err) {
      console.error('Error deleting block:', err);
      setError(err instanceof Error ? err.message : 'Network error deleting block');
    }
  }

  // Render a single block based on its type
  function renderBlock(block: Block) {
    const style = {
      padding: '0.5rem',
      borderRadius: '6px',
      cursor: 'text'
    };

    switch (block.type) {
      case 'heading':
        return <div className="noteion-block" style={style}><h2 className="noteion-heading">{block.text_content}</h2></div>;
      
      case 'code':
        return (
          <div className="noteion-block noteion-code-block">
            <pre><code>{block.text_content || ''}</code></pre>
          </div>
        );
      
      case 'bullet-list':
        const listItems = block.text_content?.split('\n').filter(line => line.trim());
        if (!listItems || listItems.length === 0) return null;
        return (
          <ul className="noteion-block noteion-bullet-list">
            {listItems.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        );
      
      case 'image':
        const imageUrl = block.text_content;
        if (!imageUrl) return null;
        return (
          <div className="noteion-block noteion-image-block">
            <img src={imageUrl} alt="Block content" className="noteion-image" />
          </div>
        );
      
      default: // text
        return <p className="noteion-block noteion-text">{block.text_content || ''}</p>;
    }
  }

  if (isLoading) {
    return <div className="loading-spinner">Loading document...</div>;
  }

  if (error) {
    return (
      <>
        <div className="error-message">{error}</div>
        <button onClick={() => window.location.reload()}>Retry</button>
      </>
    );
  }

  if (blocks.length === 0 && !isLoading) {
    return (
      <div className="document-view empty-state">
        <h2>Welcome to your workspace</h2>
        <p>Create blocks using the toolbar or click anywhere to add content.</p>
        <BlockToolbar onInsertBlock={(type: string, content?: string) => handleCreateBlock(type, content)} />
      </div>
    );
  }

  return (
    <div className="document-view">
      <div className="blocks-container" data-nested-structure>
        {blocks.map((block) => (
          <div key={block.id} className={`noteion-block`} onMouseUp={() => handleDeleteBlock(block.id)}>
            {renderBlock(block)}
            
            {/* Hover-visible delete action */}
            <button 
              className="action-delete"
              onClick={(e: React.MouseEvent<HTMLButtonElement>) => { e.stopPropagation(); handleDeleteBlock(block.id); }}
              title="Delete block"
            >
              Delete
            </button>
          </div>
        ))}
      </div>
      
      {/* Floating toolbar for inserting blocks */}
      <BlockToolbar onInsertBlock={(type: string, content?: string) => handleCreateBlock(type, content)} />
    </div>
  );
}

export default DocumentView;
