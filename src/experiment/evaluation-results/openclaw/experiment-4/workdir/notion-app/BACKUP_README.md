# 📁 Project Backups & Notes

## Current Database Location
`database.db`
- Auto-created when first running `python backend/app.py`
- Stores all your pages, blocks, and database tables
- SQLite file format - can be inspected with tools like DB Browser for SQLite if needed

## File Backup Recommendations

### Before Making Major Changes:
```bash
cp database.db backup_database_$(date +%Y%m%d_%H%M%S).db
tar -czf project_backup.tar.gz backend/ frontend/
```

### Restore from Backup:
```bash
cp backup_database_*.db database.db
gunzip < compressed_file | tar -xv
```

## Database Reset (Start Fresh)

If you want to start over with a clean slate:

1. **Backup current data** (optional):
   ```bash
   cp database.db backup_before_reset.db
   ```

2. **Delete old database**:
   ```bash
   rm database.db
   ```

3. **Reinitialize**: Run the app again - it will auto-create tables!
   ```bash
   python backend/app.py
   ```

## SQLite Inspection Tools (Optional)

- [DB Browser for SQLite](https://sqlitebrowser.org/) - GUI tool to browse your database
- `sqlite3` command-line: `sqlite3 database.db '.schema'`
- Online viewers: https://dbdiagram.io/ or similar tools

---

## Environment Variables (Future Enhancement)

Currently not used, but here's how you'd add them:

Create `.env` file in project root:
```
FLASK_SECRET_KEY=your-secret-key-here
DATABASE_PATH=./database.db
DEBUG=true
PORT=5000
```

Then modify `backend/app.py`:  
```python
from dotenv import load_dotenv
load_dotenv()
os.environ['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
os.environ['DATABASE_URL'] = f'sqlite:///{os.getenv("DATABASE_PATH")}'
```

---

## Notes on Image Storage (Current Implementation)

- Cover images are stored as **base64-encoded BLOBs** in SQLite
- This works fine for small apps but has limitations:
  - Maximum image size: ~5MB recommended
  - Database file grows with each image added
  - Not suitable for production-scale applications

### For Production Migration:
1. Replace `cover_image` column type from BLOB to TEXT (for S3 URLs)
2. Or use separate storage service like AWS S3, Cloudinary, or local filesystem
3. Update frontend to upload files and store URL references instead of base64

---

## Version Control Notes

### Initial Git Setup:
```bash
git init
git add .
git commit -m "Initial Notion Clone with Flask + SQLite"
```

### Recommended `.gitignore` entries (already included):
- `database.db` - Don't track database file (contains user data)
- `__pycache__/`, `*.pyc` - Python bytecode files
- IDE-specific folders like `.vscode/`, `.idea/`

---

## Troubleshooting Database Issues

### "Database is locked" error:
Close any other applications that might have the database open, or restart your computer.

### Large file size (>10MB):
Consider archiving old data to external storage and running with a smaller test database first.

---

## Future Enhancement Notes

These are ideas for improving the app in future versions:

- [ ] Add proper image upload endpoint (multipart/form-data)
- [ ] Implement file-based storage instead of SQLite BLOBs
- [ ] Add user authentication with JWT tokens
- [ ] Create admin panel for managing users/content
- [ ] Add search functionality across all pages/blocks
- [ ] Implement markdown parsing from text input
- [ ] Add code block support with syntax highlighting
- [ ] Support multiple database views (table, list, gallery)
