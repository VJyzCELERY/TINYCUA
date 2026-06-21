# ❓ Frequently Asked Questions - Notion Clone

## General Usage Questions

### Q: How do I create a new page?
**A:** Click the "+ New Page" button in the left sidebar, then enter a title when prompted.

### Q: Can I edit text anywhere on the page?
**A:** Yes! Everything is editable. Just click any text and start typing to replace it.

### Q: How do I add headings (H1, H2, etc.)?
**A:** Type `# Title` or use block type `{"type":"h1","content":"Title"}` in the API.
The simplest way is just clicking an empty line and typing `## My Heading`. The editor will recognize it as a heading block.

### Q: How do I create lists?
**A:** Type `- item 1`, press Enter, then type `- item 2` for bullet points. For numbered lists, use `1. First`, `2. Second` format.

### Q: What is the "+" icon in the sidebar for?
**A:** It's a folder/file organization symbol representing your workspace pages area.

---

## Technical Questions

### Q: Why do I need to enter an email address? Can't I use no auth or local storage only?
**A:** The app uses session-based authentication (Flask sessions) for simplicity. Each "user" is identified by their unique ID in the database, which we derive from their email. This ensures each user has isolated data.
To remove this requirement, you'd need to:
1. Remove `email` field from users table
2. Change session storage mechanism to use local storage tokens
3. Add CSRF protection headers
4. Implement proper authentication flow (JWT or similar)

### Q: Where is my database? Can I backup it?
**A:** The SQLite database file (`database.db`) is created automatically in the project root directory.
To find it:
- On Linux/Mac: `ls -la /workspace/experiment-4/notion-app/database.db`
- On Windows: Check the notion-app folder for a .db file
To backup: Simply copy the `.db` file to another location. To restore, replace the existing database file.

### Q: Can I upload images? How do I add cover images?
**A:** Currently, cover images are supported via base64 encoding through API calls or browser console:
```javascript
// In browser console after loading a page:
fetch('/api/users/YOUR_USER_ID/pages/' + PAGE_ID, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({coverImage: "data:image/png;base64,..."})
});
To get base64 from an image:
1. Convert your image to base64 (online tools like https://www.base64-image.de/)
2. Or use browser console: `fetch('your-image-url').then(r => r.blob()).then(b => b.toString('base64'))`

### Q: How do I create database tables?
**A:** Database tables are created automatically when you need them:
1. Create a new page with title like "📊 My Projects"
2. Add columns as headings (e.g., `# Name`, `# Status`)
The table structure will be stored in the SQLite database.
To add rows, use API calls or future enhancements to provide UI for row addition.

### Q: What happens if I close the browser? Will my data persist?
**A:** Yes! All your content is saved automatically to the SQLite database (`database.db`). Just reopen the app and you'll find all your pages intact. No manual "save" button needed!

---

## API Questions (For Developers)

### Q: What does `pageId` vs `userId` mean in API responses?
**A:** 
- `pageId`: The unique identifier for a specific page (integer, stored as string in JSON response)
- `userId`: Your user's ID from the database (derived from your email login)

### Q: Can I nest pages under other pages?
**A:** Technically yes, but this feature isn't fully implemented yet. The current implementation only supports root-level pages.
To add nested page support:
1. Modify `pages` table to allow any parent_page_id (not just NULL or self-reference)
2. Update frontend to handle hierarchical navigation
3. Add breadcrumb/up functionality for navigating back up the hierarchy

### Q: What block types are supported?
**A:** Currently supported:
- `text` - Regular paragraph text
- `h1`, `h2`, `h3` - Headings at different levels
- `quote` - Blockquotes (for tips, callouts)
- `bullet-list` / `number-list` - Lists with newline-separated items
Future additions could include:
- Code blocks
- Toggle lists
- Callout boxes
- Tables within pages

### Q: How do I update all blocks in a page at once?
**A:** Use the PUT endpoint:
```bash
curl -X PUT http://localhost:5000/api/users/YOUR_USER_ID/pages/PAGE_ID \
  -H "Content-Type: application/json" \
  -d '{"blocks": [{"type":"h2","content":"## New Title"}, {"type":"text","content":"Some text"}]}'
```
This replaces all existing blocks with the new array provided.
To preserve some blocks and update others, you'd need to fetch current blocks first, modify them in your code, then send back the complete list.

---

## Troubleshooting Questions

### Q: "Module not found" error when running `python backend/app.py`?
**A:** You're missing Python dependencies. Run:
```bash
pip install flask flask-cors click python-dotenv
```
Or use the requirements file:
```bash
pip install -r requirements.txt
```

### Q: Port 5000 already in use error?
**A:** Another application is using port 5000. Either:
1. Stop whatever's using that port (check with `lsof -i :5000` on Linux/Mac or Task Manager on Windows)
2. Or change the port by editing line ~348 in `backend/app.py`: Change `port=5000` to your desired port number

### Q: Page not showing after creating it?
**A:** Try:
1. Check browser console (F12 → Console tab) for errors
2. Verify you're on the correct page by clicking sidebar items
3. If using API calls, ensure you're getting valid JSON responses from backend
4. Clear browser cache and reload
5. Check that the page was actually created: `sqlite3 database.db "SELECT * FROM pages;"`

### Q: Content not appearing immediately after typing?
**A:** The app saves changes to SQLite automatically on each block creation/update, but there might be a slight delay due to:
1. Browser rendering lag (refresh page or click away then back)
2. Network latency if running remotely (not local development)
3. Database connection issues (check for errors in console/logs)

### Q: Images not displaying after uploading?
**A:** Image upload via base64 encoding might fail due to:
1. Base64 string too long or malformed - use smaller images (< 500KB recommended)
2. Incorrect MIME type detection on frontend (ensure you're sending correct Content-Type header)
3. Database BLOB field size limit increase may be needed for larger images

---

## Security Questions

### Q: Is my data encrypted?
**A:** Currently, no encryption is applied to stored data in the SQLite database or session cookies.
For production use:
1. Enable HTTPS/TLS (use reverse proxy like Nginx with SSL certificates)
2. Encrypt sensitive fields if needed (e.g., passwords - though currently not used)
3. Consider using encrypted databases or external storage services

### Q: Can multiple people share the same database?
**A:** Not in current implementation. Each "user" is tied to their email login, and data is stored per-user.
To enable multi-user sharing:
1. Add `shared_with_users` column to pages table (many-to-many relationship)
2. Implement permission levels (read-only vs read-write access)
3. Store shared content in separate collection linked via user IDs
4. Handle concurrent writes with database locking or optimistic concurrency control

### Q: What if I accidentally delete all my data?
**A:** SQLite databases are transactional and atomic, but accidents happen:
To recover:
1. Check for any backup files you created (look for `backup_*.db`)
2. Use SQLite recovery tools like `.recover` command in sqlite3 CLI
3. On Windows: Try to restore from System Restore Point if it was backed up there
4. For local development, consider keeping periodic backups of the database file

---

## Performance Questions

### Q: How many pages/blocks can I create?
**A:** With SQLite on modern systems:
- Pages: Millions theoretically (practical limit ~100K for good performance)
- Blocks per page: Thousands possible, but each additional block adds slight overhead
- Database file size: Can grow to gigabytes if storing large images as base64
Recommended practice:
- Keep pages under 50 blocks each for best UI responsiveness
- Use cover images sparingly (they add storage bloat)
- Archive old content periodically by exporting and creating new database

### Q: Is it slow when I have many pages?
**A:** Performance depends on page count. For <100 pages, performance is snappy.
For larger collections:
1. Consider archiving older/less-used pages to separate database
2. Implement pagination in sidebar for large page lists
3. Add search/filter functionality instead of showing all pages at once
4. Use index on `updated_at` column (already done by SQLite)
5. Migrate from SQLite BLOB storage to external file-based image storage

---

## Development Questions

### Q: Can I customize the UI/styles?
**A:** Absolutely! Edit these files:
- `/frontend/public/css/style_enhanced.css` - All styling (colors, fonts, spacing)
- Modify CSS variables or add custom classes for theming support
- Change sidebar width in `.sidebar { width: 260px; }`
- Customize colors by changing `#ea4c9d` to your preferred accent color

### Q: Can I integrate this with a framework like React/Vue?
**A:** Yes! The Flask API endpoints are RESTful and can be consumed by any frontend:
To migrate to React/Vue:
1. Keep the backend as-is (or containerize it)
2. Replace `frontend/public/` folder with your SPA build
3. Update routes in your new framework to call same `/api/*` endpoints
4. Or run both Flask and your SPA separately, proxying API calls through them
5. Consider using GraphQL instead of REST if you want more flexibility

### Q: How do I add a new block type (e.g., code blocks)?
**A:** Steps to implement:
1. **Backend (`backend/app.py`)**: Add support in `create_block()` and update schema if needed
2. **Frontend (`frontend/public/js/app_enhanced.js`)**: Update `renderSingleBlock()` with new case for block type
3. **CSS** (if needed): Add custom styling for the new block element
Example - adding code blocks:
```javascript
case 'code': 
    output += `<pre><code class="contenteditable" contenteditable="true">${this.escapeHtml(block.content)}</code></pre>`;
    break;
```
Then handle in backend similarly when receiving `{type:"code",content:...}`.

---

## Getting Help Beyond This FAQ

### For Development Issues:
- Check console logs (F12 → Console tab)
- Review API responses in Network tab of DevTools
- Examine database schema with SQLite CLI queries
- Read `ARCHITECTURE.md` for deeper understanding

### For Usage Questions:
- Consult `README.md` and `Instruction.md`
- Check `NOTES.md` for tips and tricks
- Review API documentation in README.md endpoint reference section

---

**Still have questions?** Open an issue or PR on the project repository!
