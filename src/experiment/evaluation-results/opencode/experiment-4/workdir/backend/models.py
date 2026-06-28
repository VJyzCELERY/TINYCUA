from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class Page(Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, default="")
    parent_page_id = Column(Integer, ForeignKey("pages.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Blocks for this page (one-to-many relationship)
    blocks = relationship("Block", back_populates="page")


class Block(Base):
    __tablename__ = "blocks"

    id = Column(Integer, primary_key=True)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    type = Column(String(50), nullable=False)  # 'paragraph', 'heading_1', 'heading_2', 'bulleted_list_item', etc.
    data = Column(Text, default="")  # JSON-like string for block-specific properties
    created_at = Column(DateTime, default=datetime.utcnow)

    page = relationship("Page", back_populates="blocks")