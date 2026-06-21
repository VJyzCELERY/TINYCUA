import { useState, useEffect } from 'react';
import axios from 'axios';
import './PageEditor.css';

export default function PageEditor({ pageId }) {
  const [pageData, setPageData] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [isDirty, setIsDirty] = useState(false);
  
  useEffect(() => {
    if (pageId) {
      loadPage(pageId);
      
      // Simulate loading from API or localStorage
      setTimeout(() => {
        const saved = JSON.parse(localStorage.getItem(`notion_page_${pageId}`) || 'null');
        
        if (saved && !isDirty) {
          setPageData(saved.pageData);
          setBlocks(JSON.parse(saved.blocks));
        } else if (!pageData) {
          // Create default blocks for new page
          const initialBlocks = [
            { 
              id: 'block-1', 
              type: 'text', 
              text_content: '',
              color: 'default' 
            },
            { 
              id: 'block-2', 
              type: 'heading_1', 
              text_content: '# Heading 1 Example',
              color: 'default' 
            }
          ];
          
          setBlocks(initialBlocks);
        }
      }, 0);
    }
    
    return () => {};
  }, [pageId, pageData]);

  const loadPage = async (id) => {
    try {
      
      // Try to fetch from API first
      if (!pageData && !localStorage.getItem(`notion_page_${id}`)) {
        console.log('Would call: GET /api/pages/' + id);
        
        // For demo, create page if doesn't exist
        const response = await axios.get('/api/pages/' + encodeURIComponent(id));
        setPageData(response.data);
      } else {
        // Load from localStorage or use empty state
        const saved = JSON.parse(localStorage.getItem(`notion_page_${id}`) || 'null');
        
        if (saved?.pageData) {
          setPageData(saved.pageData);
          
          const blockStr = saved.blocks;
          setBlocks(blockStr ? typeof blockStr === 'string' ? JSON.parse(blockStr) : blockStr : []);
        } else {
          // Empty page - create default blocks
          setBlocks([
            { 
              id: `block-${Date.now()}-1`, 
              type: 'text', 
              text_content: '',
              color: 'default' 
            },
            { 
              id: `block-${Date.now()}-2`, 
              type: 'heading_1', 
              text_content: '# Add a heading here...',
              color: 'default' 
            }
          ]);
        }
      }

    } catch (error) {
      console.error('Error loading page:', error);
      
      // Use default blocks if API fails
      setBlocks([
        { id: `block-${Date.now()}-1`, type: 'text', text_content: '', color: 'default' },
        { 
          id: `block-${Date.now()}-2`, 
          type: 'heading_1', 
          text_content: '# Welcome to NoteSpace!',
          color: 'default' 
        }
      ]);
    }
  };

  const handleBlockChange = (index, content) => {
    const newBlocks = [...blocks];
    
    if (!newBlocks[index]) {
      // Add new block at the end
      setBlocks([...newBlocks, createEmptyBlock()]);
      return;
      
    } else if (content === '' && !isDirty && blocks.length > 1) {
      // Remove empty block if not dirty and has multiple blocks
      const removed = newBlocks.splice(index, 1);
      setBlocks(newBlocks);
      return;
      
    } else if (!newBlocks[index] || content !== newBlocks[index].text_content) {
      // Update existing or add new
      if (content === '') {
        newBlocks.splice(index, 1);
        setIsDirty(true);
      } else {
        const block = createEmptyBlock();
        
        // Preserve type and color from previous block if available
        if (!block.type && index > 0) {
          block.type = blocks[index - 1]?.type || 'text';
        }
        
        newBlocks.splice(index, 1);
      }
      
      setBlocks([...newBlocks, createEmptyBlock()]);
    } else {
      // Update existing block content only if different
      const currentContent = typeof newBlocks[index].text_content === 'string' 
        ? newBlocks[index].text_content.replace(/\n$/, '') 
        : '';
        
      if (currentContent !== content) {
        setIsDirty(true);
      }
    }
    
    // Sync to localStorage
    syncToStorage();
  };

  const createEmptyBlock = () => ({
    id: `block-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    type: 'text',
    text_content: '',
    color: 'default'
  });

  // Block types mapping to React components
  const getBlockComponent = (type) => {
    switch(type) {
      case 'heading_1': return <h1 className="block-heading-1" contentEditable onInput={e => handleBlockChange(0, e.currentTarget.innerText)}>{blocks[0]?.text_content || ''}</h1>;
      
      case 'heading_2': return <h2 className="block-heading-2" contentEditable onInput={e => handleBlockChange(0, e.currentTarget.innerText)}>{blocks[0]?.text_content || ''}</h2>;
      
      case 'heading_3': return <h3 className="block-heading-3" contentEditable onInput={e => handleBlockChange(0, e.currentTarget.innerText)}>{blocks[0]?.text_content || ''}</h3>;
      
      default: 
        // Paragraph or text block
        const currentContent = typeof blocks?.[0]?.text_content === 'string' 
          ? blocks[0].text_content.replace(/\n$/, '') 
          : '';
          
        return (
          <p className="block-text" contentEditable onInput={e => handleBlockChange(0, e.currentTarget.innerText)}>
            {currentContent}
          </p>
        );
    }
  };

  const syncToStorage = () => {
    if (!pageId) return;
    
    localStorage.setItem(`notion_page_${pageId}`, JSON.stringify({
      pageData: pageData,
      blocks: JSON.stringify(blocks),
      isDirty: true
    }));
  };

  useEffect(() => {
    syncToStorage();
  }, [blocks]);

  return (
    <div className="editor-page">
      {/* Page Header */}
      <header className="page-header" contentEditable suppressContentEditableWarning onInput={(e) => handleBlockChange(0, e.currentTarget.innerText)}>
        {(() => {
          const title = blocks?.[0]?.text_content || '';
          
          // Auto-detect heading level based on first block type or default to paragraph
          return (
            <>
              <div className="page-title">{title}</div>
              
              {/* Icon and cover would go here */}
              <div className="page-meta">
                <span className="meta-icon-placeholder" title="Add icon"></span>
                <span className="meta-emoji-picker" title="Emoji picker coming soon">😀</span>
              </div>
            </>
          );
        })()}
      </header>

      {/* Content */}
      {(() => {
        const contentBlocks = blocks.slice(1); // Skip first block (title)
        
        if (!contentBlocks.length && !blocks[0]) {
          return <div className="empty-content">Start writing...</div>;
        }
        
        return contentBlocks.map((block, index) => {
          const currentContent = typeof block.text_content === 'string' 
            ? block.text_content.replace(/\n$/, '') 
            : '';
          
          let Component;
          
          if (index < blocks.length - 1 || !blocks[index + 1]) {
            // Not last block or no next block, render contentEditable
            switch(block.type) {
              case 'heading_1': return <h1 className="block-heading-1" key={block.id} contentEditable onInput={(e) => handleBlockChange(index + 1, e.currentTarget.innerText)}>{currentContent}</h1>;
              
              case 'heading_2': return <h2 className="block-heading-2" key={block.id} contentEditable onInput={(e) => handleBlockChange(index + 1, e.currentTarget.innerText)}>{currentContent}</h2>;
              
              case 'heading_3': return <h3 className="block-heading-3" key={block.id} contentEditable onInput={(e) => handleBlockChange(index + 1, e.currentTarget.innerText)}>{currentContent}</h3>;
              
              default: 
                Component = <p className="block-text" key={block.id} contentEditable onInput={(e) => handleBlockChange(index + 1, e.currentTarget.innerText)}></p>;
                
                // Insert cursor at end of paragraph
                setTimeout(() => {
                  const el = document.querySelector(`[contenteditable]:has([id="${block.id}]")`);
                  if (el) {
                    const range = document.createRange();
                    const sel = window.getSelection();
                    
                    range.selectNodeContents(el);
                    range.collapse(false);
                    
                    sel.removeAllRanges();
                    sel.addRange(range);
                  }
                }, 0);
                
            }
          } else {
            // Last block, read-only display
            switch(block.type) {
              case 'heading_1': return <h1 className="block-heading-1" key={block.id}>{currentContent}</h1>;
              
              case 'heading_2': return <h2 className="block-heading-2" key={block.id}>{currentContent}</h2>;
              
              case 'heading_3': return <h3 className="block-heading-3" key={block.id}>{currentContent}</h3>;
              
              default: 
                Component = <p className="block-text" key={block.id}>{currentContent}</p>;
            }
          }
          
          return <React.Fragment key={block.id} style={{ minHeight: '1em' }}>{Component || null}</React.Fragment>;
        });
      })()}

      {/* Bottom create button */}
      <button className="btn-create-block" onClick={() => handleBlockChange(blocks.length)}>
        + Add block
      </button>
    </div>
  );
}
