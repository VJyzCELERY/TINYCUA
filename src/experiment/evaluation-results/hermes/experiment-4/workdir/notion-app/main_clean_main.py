#!/usr/bin/env python3
"""Notion-like App - Flask Backend with SQLite Storage."""

import uuid, os, sys
from flask import Flask, request, jsonify as json_resp
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey, func, and_, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, joinedload

app = Flask(__name__)
DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# Database Models defined inline for simplicity
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True)
    name = Column(String(100))
    created_at = Column(DateTime, default=func.now())


class Page(Base):
    __tablename__ = 'pages'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text)
    content_type = Column(String(50))  # page, docx, pdf, etc.
    parent_id = Column(String(36), ForeignKey('pages.id'), nullable=True)
    
    blocks = relationship("Block", back_populates="page")
    comments = relationship("Comment", back_populates="page")
    created_at = Column(DateTime, default=func.now())


class Block(Base):
    __tablename__ = 'blocks'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id = Column(String(36), ForeignKey('pages.id'), nullable=False)
    type = Column(String(50))  # heading1, heading2, heading3, bullet_list_item, numbered_list_item, paragraph, code, quote, todo
    text = Column(Text, nullable=True)
    language = Column(String(100), nullable=True)  # for code blocks
    
    children_ids = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class Comment(Base):
    __tablename__ = 'comments'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id = Column(String(36), ForeignKey('pages.id'), nullable=False)
    user_id = Column(String(36))
    content = Column(Text, nullable=False)
    
    created_at = Column(DateTime, default=func.now())


# Create database tables
Base.metadata.create_all(engine)


def escape_html(text):
    """Safely escape HTML text."""
    if not text or not isinstance(text, str):
        return ''
    import html as h
    return h.escape(str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def get_page_with_blocks(page_id):
    """Fetch a page with all its blocks and nested content."""
    session = SessionLocal()
    
    try:
        # Fetch the page with all its blocks, ordered by creation time (newest first)
        from sqlalchemy.orm import joinedload
        
        page_query = Page.query.options(joinedload(Page.blocks), joinedload(Pages.comments)).filter(
            and_(Page.id == page_id)
        ).first() or None
        
        if not page_query:
            return None, 'Page not found'
        
        blocks_list = []
        
        for block in (page_query.blocks or []) or []:
            child_ids_str = getattr(block, 'children_ids', '') or ''
            
            # Only include non-empty text blocks as children (paragraphs are implicit list children)
            try:
                for child_block in ((page_query.blocks or []) or []):
                    if not hasattr(child_block, 'text') or not child_block.text:
                        continue
                    
                    child_dict = {
                        'id': escape_html(child_block.id),
                        'type': '',  # Children are paragraphs by default for lists
                        'text': escape_html(child_block.text)
                    }
                    
                    blocks_list.append(child_dict)
            except Exception as e:
                print(f"Error processing page {page_query.id}: {e}")
            
            # Add the main block (heading/list item with its text) if it has content
            if hasattr(block, 'text') and block.text:
                child_ids_str = getattr(block, 'children_ids', '') or ''
                
                block_dict = {
                    'id': escape_html(block.id),
                    'type': block.type if block.type else '',
                    'text': escape_html(block.text) if hasattr(block, 'text') and block.text else None,
                    'language': getattr(block, 'language', None),
                    'children_ids': child_ids_str.split(',') if ',' in (child_ids_str or '') else []
                }
                
                blocks_list.insert(0, block_dict)  # Insert at beginning to maintain newest-first order
        
        page_data = {
            'id': escape_html(page_query.id),
            'title': escape_html(page_query.title) if hasattr(page_query, 'title') and page_query.title else '',
            'content_type': getattr(page_query, 'content_type', None),
            'blocks': blocks_list,
            'created_at': page_query.created_at.isoformat() if hasattr(
                page_query.created_at, 'isoformat'
            ) else str(page_query.created_at) or ''
        }
        
        return (page_data, None)
    finally:
        session.close()


def get_pages():
    """Get all pages with their blocks."""
    session = SessionLocal()
    
    try:
        from sqlalchemy.orm import joinedload
        
        # Fetch all pages with their blocks, ordered by creation time (newest first)
        pages_query = Page.query.options(joinedload(Page.blocks)).order_by(
            Page.created_at.desc()
        ).all() or []
        
        result = []
        
        for page in pages_query:
            # Fetch all non-empty blocks with text for this page, ordered by creation time (newest first)
            from sqlalchemy import and_ as sql_and
            
            blocks_list = Block.query.filter(
                Block.page_id == page.id,
                sql_and(Block.text.isnot(None), Block.text != '')  # Only include blocks with actual content
            ).order_by(Block.created_at.desc()).all() or []
            
            block_dicts = []
            
            for i, block in enumerate(blocks_list):
                child_ids_str = getattr(block, 'children_ids', None) if hasattr(block, 'children_ids') else ''
                
                # Only include children that have text (paragraphs are implicit list children)
                try:
                    for child_block in blocks_list[i+1:i+6]:  # Get up to next 5 siblings after this block
                        if not hasattr(child_block, 'text') or not child_block.text:
                            continue
                        
                        child_dict = {
                            'id': escape_html(child_block.id),
                            'type': '',  # Children are paragraphs by default for lists
                            'text': escape_html(child_block.text)
                        }
                        
                except Exception as e:
                    print(f"Error processing page {page.id}: {e}")
                
            result.append({
                'id': escape_html(page.id),
                'title': escape_html(page.title or '(Untitled)'),
                'content_type': getattr(page, 'content_type', None),
                'blocks': block_dicts if len(block_dicts) > 0 else [],
                'created_at': page.created_at.isoformat() if hasattr(
                    page.created_at, 'isoformat'
                ) else str(page.created_at) or ''
            })
        
        return result
    finally:
        session.close()


def create_page(data):
    """Create a new page."""
    
    title = data.get('title') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'title', None))
    parent_id = data.get('parent_id') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'parent_id', None))
    
    # Title is required for root pages (pages without a parent or with content_type != 'page')
    if not title:
        return {'error': 'Title is required'}, 400
    
    new_page = Page(
        title=title,
        content_type=data.get('content_type', None) if isinstance(data, dict) else getattr(data, 'content_type'),
        parent_id=None  # Root page by default (parent_id will be set on child pages later)
    )
    
    session = SessionLocal()
    
    try:
        session.add(new_page)
        session.commit()
        
        return {
            'id': new_page.id,
            'title': escape_html(new_page.title),
            'content_type': getattr(new_page, 'content_type', None),
            'created_at': new_page.created_at.isoformat() if hasattr(
                new_page.created_at, 'isoformat'
            ) else str(new_page.created_at) or ''
        }, 201
    finally:
        session.close()


def get_page(page_id):
    """Get a specific page with its blocks."""
    
    from sqlalchemy.orm import joinedload
    
    session = SessionLocal()
    
    try:
        # Fetch the page with all its blocks, ordered by creation time (newest first)
        page_with_blocks = Page.query.options(
            joinedload(Page.blocks),
            joinedload(Pages.comments)  # Also load comments if needed later
        ).filter(and_(Page.id == page_id)).first() or None
        
        if not page_with_blocks:
            return {'error': 'Page not found'}, 404
        
        blocks_list = []
        
        for block in (page_with_blocks.blocks or []) or []: