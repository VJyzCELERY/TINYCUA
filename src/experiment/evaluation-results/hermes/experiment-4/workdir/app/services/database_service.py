from sqlalchemy.orm import Session
from app.models import User, Block, Page, Database, DatabaseEntry, Comment


class DatabaseService:
    """Service for managing pages, blocks, and databases"""

    @staticmethod
    def create_page(db: Session, user_id: int, title: str = None):
        page = Page(
            user_id=user_id,
            parent_block_id=None if not hasattr(Page, 'parent_block_id') else None,
            title=title or "Untitled",
            icon="📄"
        )
        db.add(page)
        db.commit()
        return page

    @staticmethod
    def get_page(db: Session, page_id: int):
        return db.query(Page).filter(Page.id == page_id).first()

    @staticmethod
    def get_all_pages(db: Session, user_id: int = None):
        if user_id:
            pages = db.query(Page).filter(Page.user_id == user_id).all()
        else:
            pages = db.query(Page).order_by(Page.created_at.desc()).all()
        
        # Include blocks for each page (if needed)
        result = []
        for page in pages:
            blocks = db.query(Block).filter(Block.page_id == page.id).all() if hasattr(Block, 'page_id') else []
            result.append({
                **dict(page),
                "blocks": [dict(b) for b in blocks]
            })
        
        return result

    @staticmethod
    def get_page_blocks(db: Session, page_id: int):
        """Get all blocks belonging to a specific page"""
        if not hasattr(Block, 'page_id'):
            return []
        return db.query(Block).filter(Block.page_id == page_id).all()
