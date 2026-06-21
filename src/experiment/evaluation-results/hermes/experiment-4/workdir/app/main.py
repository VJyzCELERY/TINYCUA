from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List

# Import services and models (placeholder for now)
from app.services.database_service import DatabaseService


app = FastAPI(title="Notion Clone", version="1.0")

templates = Jinja2Templates(directory="static/templates")


@app.get("/")
def read_root():
    return templates.TemplateResponse("index.html", {"request": None})


# Pages API
@app.post("/api/pages/")
async def create_page(page_id: int, title: str):
    """Create a new page"""
    service = DatabaseService()
    page = service.create_page(user_id=page_id)  # Simplified for demo
    return {"id": page.id, "title": page.title}


@app.get("/api/pages/{page_id}")
async def get_page(page_id: int):
    """Get a specific page"""
    page = DatabaseService().get_page(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"title": page.title, "blocks": page.blocks}


@app.get("/api/pages/")
async def get_all_pages():
    """Get all pages"""
    pages = DatabaseService().get_all_pages()
    return [{"id": p.id, "title": p.title} for p in pages]


# Blocks API
@app.post("/api/blocks/")
async def create_block(block_data: dict):
    """Create a new block (text, heading, etc.)"""
    service = DatabaseService()
    block = service.create_block(**block_data)
    return {"id": block.id, "type": block.type}


# Databases API
@app.post("/api/databases/")
async def create_database(database_data: dict):
    """Create a new database/table"""
    service = DatabaseService()
    db = service.create_database(**database_data)
    return {"id": db.id, "title": db.title}


# Auth (placeholder - would need auth system)
@app.post("/api/auth/login")
async def login(username: str, password: str):
    """Login endpoint"""
    # TODO: Implement proper authentication
    return {"message": f"Logged in as {username}", "token": "demo-token"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
