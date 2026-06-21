from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


# Users table
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# Pages table - main document pages (like Notion pages)
class Page(Base):
    __tablename__ = 'pages'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    parent_block_id = Column(Integer, ForeignKey('blocks.id'), nullable=True)  # For nested pages in blocks (coming soon)
    title = Column(String(255), nullable=False)
    
    # Optional cover image URL
    icon = Column(String(100), nullable=True)  # Emoji or custom icon
    
    created_at = Column(DateTime, default=datetime.utcnow)


# Blocks table - stores all content blocks (text, headings, paragraphs, etc.)
class Block(Base):
    __tablename__ = 'blocks'
    
    id = Column(Integer, primary_key=True)
    page_id = Column(Integer, ForeignKey('pages.id'), nullable=False)
    parent_block_id = Column(Integer, ForeignKey('blocks.id'), nullable=True)  # For nested blocks like lists
    
    type = Column(String(50), nullable=False)  # 'text', 'heading_1', 'heading_2', 'paragraph', 'bullet_list_item'
    text = Column(Text, nullable=True)
    
    is_checked = Column(Integer, default=0)  # For checkboxes (0 or 1)


# Databases table - for Notion-like databases (tables with properties/columns)
class Database(Base):
    __tablename__ = 'databases'
    
    id = Column(Integer, primary_key=True)
    page_id = Column(Integer, ForeignKey('pages.id'), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(100), nullable=True)  # Emoji or custom icon
    
    created_at = Column(DateTime, default=datetime.utcnow)


# Database entries table - rows in the database
class DatabaseEntry(Base):
    __tablename__ = 'database_entries'
    
    id = Column(Integer, primary_key=True)
    database_id = Column(Integer, ForeignKey('databases.id'), nullable=False)
    title = Column(String(255), nullable=False)
    page_id = Column(Integer, ForeignKey('pages.id'))  # Link back to the parent page
    
    created_at = Column(DateTime, default=datetime.utcnow)


# Comments table - for collaborative features
class Comment(Base):
    __tablename__ = 'comments'
    
    id = Column(Integer, primary_key=True)
    block_id = Column(Integer, ForeignKey('blocks.id'), nullable=True)
    page_id = Column(Integer, ForeignKey('pages.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# Bookmarks table - for linking to external resources (like Notion links from web)
class Bookmark(Base):
    __tablename__ = 'bookmarks'
    
    id = Column(Integer, primary_key=True)
    page_id = Column(Integer, ForeignKey('pages.id'), nullable=False)
    title = Column(String(255), nullable=False)
    url = Column(String(1024), nullable=False)
    description = Column(Text, nullable=True)

