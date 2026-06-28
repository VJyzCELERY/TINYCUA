import { useEditor, EditorContent, type Editor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { useCallback, useEffect, useRef } from 'react'

// Block type matching backend API
export interface Block {
  id: string;
  type: 'text' | 'code' | 'heading' | 'image' | 'bullet-list';
  text_content?: string;
}

interface TipTapEditorProps {
  blocks: Block[];
  onBlocksChange: (newBlocks: Block[]) => void;
  onDeleteBlock: (blockId: string) => void;
  onSaveCallback?: () => void; // For backend sync
}

export function TipTapEditor({ 
  blocks, 
  onBlocksChange, 
  onDeleteBlock,
  onSaveCallback 
}: TipTapEditorProps) {
  const editorRef = useRef<Editor | null>(null);

  // Initialize and manage editor instance
  useEffect(() => {
    if (!editorRef.current) {
      editorRef.current = useEditor({
        extensions: [
          StarterKit,
          Placeholder.configure({ placeholder: 'Type "/" for commands...' }),
        ],
        onUpdate: ({ editor }) => {
          // Optional: Save to backend via onSaveCallback on changes
          if (onSaveCallback) {
            onSaveCallback();
          }
          
          // Sync blocks when editor updates
          const newBlocks = serializeEditorToBlocks(editor);
          onBlocksChange(newBlocks);
        },
      });

      return () => {
        if (editorRef.current) {
          editorRef.current.destroy();
        }
      };
    }
  }, [onSaveCallback, onBlocksChange]);

  // Sync blocks to editor content when blocks prop changes
  useEffect(() => {
    if (!editorRef.current || blocks.length === 0) return;

    const htmlContent = serializeBlocksToHtml(blocks);
    editorRef.current.commands.setContent(htmlContent);
    
    // Trigger onBlocksChange after sync
    const newBlocks = serializeEditorToBlocks(editorRef.current);
    onBlocksChange(newBlocks);
  }, [blocks]);

  // Serialize blocks array to HTML for TipTap
  function serializeBlocksToHtml(blocks: Block[]): string {
    let htmlContent = '';
    
    for (const block of blocks) {
      switch (block.type) {
        case 'heading':
          if (block.text_content) {
            htmlContent += `<h2>${escapeHtml(block.text_content)}</h2>\n`;
          }
          break;
        case 'code':
          if (block.text_content) {
            htmlContent += `<pre><code>${escapeCode(block.text_content)}</code></pre>\n`;
          }
          break;
        case 'bullet-list': {
          const items = block.text_content?.split('\n').filter(line => line.trim()) || [];
          if (items.length > 0) {
            htmlContent += `<ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>\n`;
          }
          break;
        }
        case 'image':
          if (block.text_content) {
            htmlContent += `<img src="${escapeHtml(block.text_content)}" alt="Block image">\n`;
          }
          break;
        default: // text
          if (block.text_content) {
            htmlContent += `${escapeHtml(block.text_content)}\n`;
          }
      }
    }

    return htmlContent || '<p>Start typing...</p>';
  }

  // Serialize TipTap editor HTML back to blocks array for sync
  function serializeEditorToBlocks(editor: Editor): Block[] {
    const newBlocks: Block[] = [];
    let content = editor.getHTML();
    
    // Simple parser - split by double newlines for block separation
    while (content.includes('\n\n')) {
      const parts = content.split('\n\n');
      if (parts.length < 2) break;

      for (const part of parts.slice(0, -1)) {
        parseBlock(part.trim(), newBlocks);
      }
      content = parts[parts.length - 1];
    }
    
    // Parse remaining content
    parseBlock(content.trim() || '', newBlocks);
    
    return newBlocks;
  }

  function parseBlock(text: string, blocks: Block[]): void {
    if (!text) return;
    
    let type: 'text' | 'code' | 'heading' | 'image' | 'bullet-list' = 'text';
    let content = '';

    const headingMatch = text.match(/<h2>(.*?)<\/h2>/);
    const codeMatch = text.match(/<pre><code>([\s\S]*?)<\/code><\/pre>/);
    const imageMatch = text.match(/src="([^"]*)"/i);
    
    if (headingMatch) {
      type = 'heading';
      content = headingMatch[1];
    } else if (codeMatch) {
      type = 'code';
      content = codeMatch[1].replace(/</g, '&lt;').replace(/>/g, '&gt;');
    } else if (imageMatch) {
      type = 'image';
      content = imageMatch[1];
    }

    blocks.push({
      id: `block-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      type,
      text_content: content || undefined,
    });
  }

  // Escape functions for different block types
  function escapeHtml(text: string): string {
    return (text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function escapeCode(text: string): string {
    return (text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\n/g, '\\n').replace(/	/g, '\	');
  }

  // Handle undo via TipTap's native commands (StarterKit includes history)
  const handleUndo = useCallback(() => {
    editorRef.current?.chain().undo().run();
  }, []);

  // Handle redo via TipTap's native commands
  const handleRedo = useCallback(() => {
    editorRef.current?.chain().redo().run();
  }, []);

  // Handle block deletion - delete all blocks by calling onDeleteBlock with empty string
  const handleClearDocument = useCallback(() => {
    if (!onDeleteBlock) return;
    
    window.confirm('Are you sure you want to clear the entire document?') && 
      onDeleteBlock('');
  }, [onDeleteBlock]);

  // Check for undo/redo capability via editor commands availability
  const canUndo = typeof editorRef.current?.commands.undo === 'function';
  const canRedo = typeof editorRef.current?.commands.redo === 'function';
  
  return (
    <div className="tipTap-editor-container">
      {/* Editor content area */}
      {editorRef.current && (
        <EditorContent editor={editorRef.current} className="tiptap-content" />
      )}
      
      {/* Action buttons toolbar - separate from BlockToolbar component */}
      <div className="action-toolbar">
        {canUndo && (
          <button 
            type="button" 
            className="toolbar-action undo-btn"
            onClick={handleUndo}
            title="Undo"
          >
            ↶ Undo
          </button>
        )}
        
        {canRedo && (
          <button 
            type="button" 
            className="toolbar-action redo-btn"
            onClick={handleRedo}
            title="Redo"
          >
            ↷ Redo
          </button>
        )}
        
        <button 
          type="button" 
          className="toolbar-action clear-btn"
          onClick={handleClearDocument}
          title="Delete all blocks"
        >
          🗑️ Clear document
        </button>
      </div>
    </div>
  )
}

export default TipTapEditor;
