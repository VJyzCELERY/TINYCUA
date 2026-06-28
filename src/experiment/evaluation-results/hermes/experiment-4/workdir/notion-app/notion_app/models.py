"""Database Models for Notion-like App"""
import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
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
    
    children_ids = Column(String(500), nullable=True)  # comma-separated list of block IDs (for lists)
    
    created_at = Column(DateTime, default=func.now())


class Comment(Base):
    __tablename__ = 'comments'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id = Column(String(36), ForeignKey('pages.id'), nullable=False)
    user_id = Column(String(36), ForeignKey('users.id'))
    content = Column(Text, nullable=False)
    
    created_at = Column(DateTime, default=func.now())
