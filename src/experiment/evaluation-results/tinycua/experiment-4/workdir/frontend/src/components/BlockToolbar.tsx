import { useState } from 'react'
import './BlockToolbar.css'

interface BlockToolbarProps {
  onInsertBlock: (blockType: string) => void
}

const BLOCK_TYPES = [
  { type: 'text', label: 'Text', icon: 'T' },
  { type: 'heading-1', label: 'Heading 1', icon: '#H1' },
  { type: 'heading-2', label: 'Heading 2', icon: '#H2' },
  { type: 'bullet-list', label: 'Bulleted List', icon: '•' },
  { type: 'numbered-list', label: 'Numbered List', icon: '1.' },
  { type: 'code-block', label: 'Code Block', icon: '</>' },
  { type: 'quote', label: 'Quote', icon: '"⋯"' },
  { type: 'divider', label: 'Divider', icon: '—' },
]

export function BlockToolbar({ onInsertBlock }: BlockToolbarProps) {
  const [isHovered, setIsHovered] = useState(false)

  return (
    <div
      className="block-toolbar"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className={`toolbar-content ${isHovered ? 'expanded' : ''}`}>
        {BLOCK_TYPES.map((block) => (
          <button
            key={block.type}
            type="button"
            className="toolbar-button"
            onClick={() => onInsertBlock(block.type)}
            title={block.label}
            aria-label={`Insert ${block.label}`}
          >
            <span className="toolbar-icon">{block.icon}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

export default BlockToolbar
