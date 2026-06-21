# 🎓 Getting Started Guide - Notion Clone

## Welcome! 
You've built a lightweight, intuitive **Notion-like web app** using Python Flask and SQLite. This guide will walk you through everything from first run to advanced usage.

---

## Part 1: Installation & First Run (5 Minutes)

### Step 1: Navigate to Project Directory
```bash
cd /workspace/experiment-4/notion-app
```

### Step 2: Install Python Dependencies
```bash
pip install flask flask-cors click python-dotenv --upgrade
```
Expected output:
```
Collecting flask...
Installing collected packages: Flask, flask-cors, ...
Successfully installed flask-3.0.0 flask-cors-4.0.0 ...
```

### Step 3: Run the Application
```bash
python backend/app.py
```

You should see:
```
✓ Database initialized successfully!
 * Running on http://0.0.0.0:5000
Press CTRL+C to quit
```

✅ **Success!** The app is running.

---

## Part 2: Access Your App (1 Minute)

### Open in Browser:
Go to your browser and navigate to:
**http://localhost:5000**

### First Login:
1. You'll see a login screen asking for an email address
2. Enter any email you like, e.g., `hello@example.com`
3. Click the "Continue" button
4. No password needed - it's just for local use!

✅ **You're now logged in!**

---

## Part 3: Create Your First Page (1 Minute)

### Using the UI:
1. Look at the left sidebar
2. Click "+ New Page" button
3. When prompted, enter a title like "My Notes"
4. ✨ Done! You now have your first page!

### What to See:
- The page appears in sidebar with 📝 icon (default)
- Title shows as `# My Notes` at top of editor area
- Large empty content area for typing

---

## Part 4: Start Writing Content! 

### Basic Editing - It's Intuitive!
Just click anywhere and start typing:

#### Type Headings:
```
# This is a Heading Level 1 (H1)
## This is a Heading Level 2 (H2)  
### This is a Heading Level 3 (H3)
```
The editor will automatically format these correctly!

#### Add Paragraphs:
Just type - each paragraph you add creates a new block.
Press Enter to create a new paragraph/block within same page.

#### Create Lists:
**Bullet list:**
```markdown
- Item one
- Item two  
- Item three
```

**Numbered list:**
```markdown
1. First item
2. Second item
3. Third item
```
The editor handles this automatically!

#### Add Blockquotes:
Select any text and press Tab to get `>` prefix.
Or manually type: `> This is a quote block`

---

## Part 5: Explore Your Workspace 

### Sidebar Navigation:
- Each page shows in sidebar with icon + title preview
- Click different pages to navigate between them
- Long titles are truncated (show first ~30 chars) for compact display

### Creating Multiple Pages:
1. Click "New Page" button multiple times
2. Give each a unique name: `Journal`, `Ideas`, `Projects`, etc.
3. Use icons like 📝, 🗂️, 💡 to distinguish them
4. Each page is independent - content doesn't mix!

---

## Part 6: Add Cover Images (Optional Fun!)

### Using Browser Console Method:
1. Open browser DevTools with F12 key
2. Go to "Console" tab
3. Find your user ID from API response or login data
4. Run this command after loading a page:
   ```javascript
   fetch('/api/users/YOUR_USER_ID/pages/PAGE_ID', {
       method: 'PUT',
       headers: {'Content-Type': 'application/json'},
       body: JSON.stringify({coverImage: "data:image/png;base64,...YOUR_BASE64_IMAGE..."})
   });
```
To get base64 from an image:
- Use online tool like https://www.base64-image.de/
- Or convert your own images to base64 format

### CSS Styling (Cover Images):
The app has a `.cover-image-container` class that displays cover images at top of page.
Currently covers are stored as BLOBs in SQLite database for simplicity.

---

## Part 7: Create Database Tables 

### How It Works:
Database tables let you organize content like Notion does!

1. **Create a new page** with title like `📊 My Projects`
2. **Add columns as headings:**
   ```markdown
   # Name      ← Column header (H1 or H2)
   # Status    ← Another column
   # Priority  ← Third column
   ```
3. The table structure is stored in SQLite database!
4. Add rows via API calls or future UI enhancements.

### Use Cases:
- Project tracking with Name, Status columns
- Task management with Title, Due Date, Tags
- Inventory lists with Item, Quantity, Location

---

## Part 8: Keyboard Shortcuts & Tips 

| Key | Action |
|-----|--------|
| Enter | Create new paragraph/block |
| Tab | Add quote (`>`) prefix |
| Shift+Enter | Line break within same block |
| Ctrl+C / V | Copy/paste works! ✅ |
| Delete/Backspace | Remove characters like any text editor |

### Pro Tips:
- **Auto-save:** Everything saves automatically to SQLite - no manual save needed!
- **Long documents:** Just keep typing, press Enter for new blocks
- **Formatting:** Select text and use Tab for quotes or type headings manually
- **Organization:** Create multiple pages via sidebar instead of one giant document

---

## Part 9: View Your Data (SQLite Inspection)

### Check what you've created:
```bash
sqlite3 database.db ".tables"
# Shows all tables in current SQLite file
```

Expected output:
```
database_columns    pages               users
blocks              database_tables
```

### List your pages:
```bash
sqlite3 database.db "SELECT * FROM pages;"
```
See page IDs, titles, icons, cover images (as hex data), and timestamps.

### View all blocks in a specific page:
```bash
# Replace PAGE_ID with actual ID number from previous query
sqlite3 database.db "SELECT id, type, content FROM blocks WHERE page_id=PAGE_ID ORDER BY id ASC;"
```
Shows each block's type (h1, h2, text) and its text content.

---

## Part 10: Next Steps 

### What to Do Now:
1. **Create multiple pages** for different topics/sections
2. **Try adding cover images** via browser console (see above)
3. **Build a simple database table** with columns and rows
4. **Write your first "document"** - maybe an article or notes file
5. **Experiment with headings, lists, quotes** to see all block types work

### Recommended Reading:
- `README.md` - Full features & API reference
- `Instruction.md` - Simple usage guide for beginners  
- `NOTES.md` - Tips and tricks for advanced users
- `QUICK_START.md` - Fastest way to get things done
- `FAQ.md` - Answers common questions you might have

### For Developers:
- `ARCHITECTURE.md` - Deep dive into how it works technically  
- `CONTRIBUTING.md` - How to add new features yourself  
- `TESTING.md` - Guidelines for testing your changes  
- `DEPLOYMENT.md` - Production deployment options

---

## Part 11: Troubleshooting Quick Fixes 

### Problem: "Module not found" error?
**Fix:** Install dependencies again:
```bash
pip install flask flask-cors click python-dotenv --upgrade
```

### Problem: Port already in use?
**Fix:** Either stop whatever's using port 5000, or change it:
Edit `backend/app.py` line ~348 and change to different number:
```python
app.run(debug=True, host='0.0.0.0', port=8000)  # Use different port
```

### Problem: Page not showing after creation?
**Fix:** Check browser console (F12 → Console tab) for errors, then:
- Refresh page and try again
- Verify API calls succeeded in Network tab of DevTools
- Query database directly to confirm data exists

---

## Part 12: Data Persistence & Backups 

### Your Data Location:
The SQLite file `database.db` is stored in project root directory.
All your pages, blocks, and tables are saved there automatically!

### To Backup (Before Making Changes):
```bash
cp database.db backup_$(date +%Y%m%d_%H%M%S).db
```

### To Restore from Backup:
1. Close Flask app if running (`Ctrl+C` in terminal)
2. Delete old database file: `rm database.db`
3. Copy backup back: `cp backup_file db/database.db`
4. Restart app with `python backend/app.py`
5. Your data is restored!

---

## Summary Checklist 

After reading this guide, you should be able to:
- ✅ Install and run the application locally
- ✅ Create new pages via sidebar "New Page" button  
- ✅ Type content with headings, paragraphs, lists, quotes
- ✅ Navigate between multiple pages using sidebar
- ✅ Add cover images (via browser console if desired)
- ✅ Create database tables for organizing data
- ✅ Back up and restore your SQLite database file
- ✅ Troubleshoot common issues independently

---

## You're Ready!

Congratulations! 🎉 
You now have a fully functional Notion-like app running locally with:
- Rich text editing ✍️  
- Page organization 📑
- SQLite persistence 💾
- Clean, intuitive UI 🎨

Enjoy building your workspace!
