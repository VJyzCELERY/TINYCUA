"""
Blocks CRUD endpoints for Notion-like Web Application.
Handles block manipulation including text, headings, lists, images, and formatting. """
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Page, Block  # noqa: F401
from app.schemas import (
    BlockCreate,
    BlockUpdate,
    BlockResponse,
)
import json

router = APIRouter(prefix="/blocks", tags=["Blocks"])


def get_block(db: Session, page_id: uuid.UUID, block_id: uuid.UUID) -> Optional[Block]:
    """
    Get a specific block by ID.
    
    Args:
        db: Database session
        page_id: UUID of the parent page
        block_id: UUID of the block to retrieve
        
    Returns:
        Block object or None if not found
    """
    return db.query(Block).filter(
        Block.id == block_id,
        Block.page_id == page_id,
        Block.deleted_at.is_(None)
    ).first()


def get_page_blocks(db: Session, page_id: uuid.UUID) -> list:
    """
    Get all blocks for a specific page.
    
    Args:
        db: Database session
        page_id: UUID of the parent page
        
    Returns:
        List of Block objects ordered by position_index
    """
    return sorted(
        db.query(Block).filter(
            Block.page_id == page_id,
            Block.deleted_at.is_(None)
        ).all(),
        key=lambda b: (b.position_index or float('inf'))
    )


@router.post("/{page_id}", response_model=BlockResponse, summary="Create a new block")
def create_block(
    page_id: uuid.UUID,
    position_index: int = None,  # Position to insert at (None for end)
    block_data: BlockCreate = None,
    db: Session = Depends(get_db),
):
    """
    Create a new block in a page.
    
    Args:
        page_id: UUID of the parent page
        position_index: Position to insert at (None appends to end)
        block_data: Block creation data with type and content
        db: Database session
        
    Returns:
        Created BlockResponse object
        
    Example Request Body for text block:
        {
            "block_type": "text",
            "text_content": "This is a paragraph of text."
        }
        
    Example Request Body for heading 1:
        {
            "block_type": "h1",
            "text_content": "# Main Heading"
        }
        
    Example Response:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "type": "h1",
            "text_content": "# Main Heading"
        }
    """
    if block_data is None:
        return BlockResponse(
            id=uuid.uuid4(),
            block_type="text",
            text_content=None,
            language=None,
            is_collapsed=False,
            list_style=None,
            todo_checked=False
        )
    
    # Validate block type against enum
    valid_types = [
        'text', 'h1', 'h2', 'h3',
        'bulleted_list_item', 'numbered_list_item',
        'todo', 'quote', 'code_block', 'image', 'callout'
    ]
    if block_data.block_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid block type. Valid types: {valid_types}"
        )
    
    # Get existing blocks to determine position
    existing_blocks = get_page_blocks(db, page_id)
    next_position = len(existing_blocks) if position_index is None else max(b.position_index or 0 for b in existing_blocks) + 1
    
    block = Block(
        id=block_data.id if block_data.id else uuid.uuid4(),
        page_id=str(page_id),
        block_type=block_data.block_type,
        text_content=block_data.text_content or None,
        language=block_data.language or None,
        is_collapsed=block_data.is_collapsed if hasattr(block_data, 'is_collapsed') else False,
        list_style=block_data.list_style,
        todo_checked=block_data.todo_checked if hasattr(block_data, 'todo_checked') else False,
        position_index=position_index or next_position
    )
    
    db.add(block)
    db.commit()
    db.refresh(block)
    
    return BlockResponse.model_validate(block)


@router.get("/{page_id}", response_model=list[BlockResponse], summary="Get all blocks in a page")
def list_blocks(
    page_id: uuid.UUID,
    skip: int = 0,
    limit: Optional[int] = None,  # None means no limit (all blocks)
    db: Session = Depends(get_db),
):
    """
    Get all blocks in a specific page.
    
    Args:
        page_id: UUID of the parent page
        skip: Number of records to skip for pagination
        limit: Maximum number of results (None = no limit)
        db: Database session
        
    Returns:
        List of BlockResponse objects ordered by position_index
        
    Example Response:
        [
            {
                "id": "block-id-1",
                "type": "h1",
                "text_content": "# Page Title"
            },
            {
                "id": "block-id-2",
                "type": "bulleted_list_item",
                "text_content": "• Item one"
            }
        ]
    """
    blocks = get_page_blocks(db, page_id)
    
    if limit is not None:
        blocks = blocks[skip:skip + limit]
    
    return [BlockResponse.model_validate(block) for block in blocks]


@router.get("/{page_id}/{block_id}", response_model=BlockResponse, summary="Get a specific block")
def get_block(
    page_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Get a specific block by ID.
    
    Args:
        page_id: UUID of the parent page
        block_id: UUID of the block to retrieve
        db: Database session
        
    Returns:
        BlockResponse object with full block data
        
    Raises:
        HTTPException(404): If block not found or soft-deleted
    """
    block = get_block(db, page_id, block_id)
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found in this page."
        )
    
    return BlockResponse.model_validate(block)


@router.put("/{page_id}/{block_id}", response_model=BlockResponse, summary="Update a block")
def update_block(
    page_id: uuid.UUID,
    block_id: uuid.UUID,
    block_data: BlockUpdate = None,
    db: Session = Depends(get_db),
):
    """
    Update an existing block's content and properties.
    
    Args:
        page_id: UUID of the parent page
        block_id: UUID of the block to update
        block_data: Partial data containing fields to update
        db: Database session
        
    Returns:
        Updated BlockResponse object with new values
        
    Example Request Body (partial):
        {
            "text_content": "Updated paragraph content here",
            "language": "python"
        }
    """
    if block_data is None:
        return get_block(db, page_id, block_id)
    
    block = get_block(db, page_id, block_id)
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found in this page."
        )
    
    # Update only provided fields
    if block_data.text_content is not None:
        block.text_content = block_data.text_content
    if block_data.language is not None:
        block.language = block_data.language
    if block_data.is_collapsed is not None and hasattr(block, 'is_collapsed'):
        block.is_collapsed = block_data.is_collapsed
    if block_data.list_style is not None and hasattr(block, 'list_style'):
        block.list_style = block_data.list_style
    if block_data.todo_checked is not None and hasattr(block, 'todo_checked'):
        block.todo_checked = block_data.todo_checked
    
    db.commit()
    db.refresh(block)
    
    return BlockResponse.model_validate(block)


@router.delete("/{page_id}/{block_id}", summary="Delete or restore a block")
def manage_block(
    page_id: uuid.UUID,
    block_id: uuid.UUID,
    hard_delete: bool = False,  # False = soft delete/restore
    db: Session = Depends(get_db),
):
    """
    Delete (soft) or permanently remove a block.
    
    Args:
        page_id: UUID of the parent page
        block_id: UUID of the block to manage
        hard_delete: If True, permanently deletes. Default False for soft delete/restore
        db: Database session
        
    Example Usage:
        DELETE /api/v1/blocks/{page_id}/{block_id}?hard_delete=false  # Soft restore from trash
        DELETE /api/v1/blocks/{page_id}/{block_id}?hard_delete=true   # Permanent deletion
    """
    block = get_block(db, page_id, block_id)
    
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found in this page."
        )
    
    # Soft delete or restore
    if hard_delete:
        db.delete(block)  # True permanent delete
    else:
        block.deleted_at = None  # Restore from soft-delete state
    
    db.commit()
    db.refresh(block)
    
    return BlockResponse.model_validate(block)
