"""Sample data creation for initial setup"""


def create_sample_pages(db):
    """Create sample pages with blocks"""
    
    # Home Page
    home = db.query(Page).filter_by(title="Home").first() or \
           DatabaseService.create_page(db, user_id=1, title="Home")
    
    if hasattr(home, 'blocks') and not home.blocks:
        from app.models import Block
        blocks_data = [
            {'type': 'heading_1', 'text': '# Welcome to Notion Clone'},
            {'type': 'paragraph', 'text': "This is your workspace. Use the sidebar to create new pages or databases!"},
            {'type': 'bullet_list_item', 'text': 'Create a page by clicking + in the sidebar'},
            {'type': 'bullet_list_item', 'text': 'Add content blocks using / command (coming soon)'},
        ]
