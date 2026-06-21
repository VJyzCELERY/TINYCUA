# 🔧 Troubleshooting Guide - Notion Clone

## Quick Reference Table

| Issue | Quick Fix |
|-------|----------|
| "Module not found" error | `pip install flask flask-cors click python-dotenv --upgrade` |
| Port 5000 already in use | Kill process using port OR change to different port (e.g., 8000) |
| Page not appearing after creation | Check browser console for errors, verify API call succeeded in Network tab |
| Content not saving immediately | Click away then back, or refresh page - data is still saved! |
| Cover images not displaying | Use smaller images (<5MB), check MIME type is correct |
| Database tables not working | Make sure columns are added as headings first |

---

## Detailed Troubleshooting Section

### Issue 1: "Module Not Found" / Import Error

**Symptoms:**
```
ImportError: No module named 'flask'
or ModuleNotFoundError: No module named 'flask_cors'
```

**Root Cause:** Missing Python dependencies.

**Solution Steps:**
1. Navigate to project directory:
   ```bash
   cd /workspace/experiment-4/notion-app
   ```
2. Install all required packages:
   ```bash
   pip install flask flask-cors click python-dotenv --upgrade
   ```
3. Or use requirements file (more reliable):
   ```bash
   pip install -r requirements.txt
   ```
4. Verify installation by checking versions:
   ```bash
   python -m pip list | grep -E "flask|cors"
```
5. Restart Flask app: `python backend/app.py`
6. If still failing, clear pip cache and try again:
   ```bash
   pip cache purge
   pip install flask flask-cors click python-dotenv --upgrade
   ```

---

### Issue 2: Port Already in Use

**Symptoms:**
```
Address already in use. Bind on port '5000' failed.
or OSError: [Errno 48] Address family not supported or protocol wrong
```

**Root Cause:** Another application is using port 5000 (e.g., another Flask app, development server).

**Solution Steps (Linux/Mac):**
1. Find what's using the port:
   ```bash
   lsof -i :5000 | grep LISTEN
```
2. Kill that process:
   ```bash
   kill <PID>  # Replace <PID> with actual process ID shown in previous command
   ```
3. Or change to different port by editing `backend/app.py` line ~348:
   ```python
   app.run(debug=True, host='0.0.0.0', port=8000)  # Change from 5000 to your desired port
```

**Solution Steps (Windows):**
1. Find process using the port:
   ```powershell
   netstat -ano | findstr :5000
```
2. Kill that process:
   ```powershell
   taskkill /PID <PID> /F  # Replace <PID> with actual number shown in previous command
   ```
3. Or change port as above.

---

### Issue 3: Page Not Appearing After Creation

**Symptoms:** Clicking "+ New Page" and entering title, but page doesn't show up in sidebar or editor area stays blank.

**Solution Steps:**
1. **Check browser console for JavaScript errors (F12 → Console):**
   ```javascript
   // Look for any red error messages that might explain why API call failed
   ```

2. **Verify the page was actually created in database:**
   ```bash
   sqlite3 database.db "SELECT id, title, icon FROM pages WHERE parent_page_id IS NULL ORDER BY updated_at DESC LIMIT 10;"
```
   If your new page appears here but not on screen:
   - Refresh browser (F5)
   - Clear cache and reload: Ctrl+Shift+R

3. **Check API response in Network tab:**
   - Open DevTools → Network tab
   - Look at request to `/api/users/{id}/pages` endpoint 
   - Confirm it returned status 201 Created with valid `pageId`

4. **If using custom port, verify you're accessing correct URL:**
   ```bash
   # If changed port in backend/app.py to 8000:
   http://localhost:8000  ← Not :5000!
```

---

### Issue 4: Content Not Appearing Immediately After Typing

**Symptoms:** Type text, but it doesn't show up until you click somewhere else or refresh.

**Root Cause:** Browser rendering lag with contenteditable elements is normal for this implementation.

**Solution Steps:**
1. **Click outside editor area then back in to trigger re-render** (quickest fix)
2. Or press `Ctrl+S` on some browsers forces reflow and shows changes immediately
3. Data IS being saved - you can verify:
   ```bash
   sqlite3 database.db "SELECT id, content FROM blocks WHERE page_id=YOUR_PAGE_ID ORDER BY id DESC LIMIT 5;"
```
4. For persistent issue, try adding `&?nocache` to URL and removing after first load (clears browser cache)

---

### Issue 5: Cover Images Not Displaying After Upload

**Symptoms:** Using base64 encoding via API or console, but cover image doesn't appear at top of page.

**Root Cause:** Either image too large for SQLite BLOB storage, incorrect MIME type detection, or CSS not rendering container properly.

**Solution Steps:**
1. **Use smaller images (< 500KB recommended)**:
   - Compress with online tool like https://tinypng.com/
   - Or resize to lower dimensions before converting to base64
2. **Verify MIME type is correct in response:**
   ```javascript
   // After uploading, check what the API returns for cover_image field:
   fetch('/api/users/YOUR_USER_ID/pages/PAGE_ID')
     .then(r => r.json())
     .then(d => console.log('Cover image MIME type would be in response'));
```
3. **Check CSS has proper container:** Open `style_enhanced.css` and verify `.cover-image-container` exists with correct styles
4. **Alternative: Store cover images as URLs instead of base64 BLOBs** for production:
   - Upload to external service (AWS S3, Cloudinary, Imgur)
   - Store URL string in SQLite `cover_image` field instead of binary data
5. **Clear browser cache and reload:** Sometimes cached CSS prevents new styles from rendering

---

### Issue 6: Database Tables Not Working / Rows Not Saving

**Symptoms:** Creating table with columns, but rows don't appear or API calls to add rows return errors.

**Root Cause:** Table structure might not be properly stored in SQLite's `database_tables` and `database_columns` tables.

**Solution Steps:**
1. **Verify database schema is correct:**
   ```bash
   sqlite3 database.db ".schema"
```
2. **Check if table entry exists for your "database" page:**
   ```bash
   sqlite3 database.db "SELECT * FROM database_tables;"
```
3. **If empty, recreate it via API call or manually in SQLite CLI:**
   ```sql
   INSERT INTO database_tables (user_id, title, columns_data) 
     VALUES (YOUR_USER_ID, '📊 My Projects', '{"Name": "text", "Status": "select"}');
```
4. **Verify column definitions are stored:**
   ```bash
   sqlite3 database.db "SELECT * FROM pages WHERE title='Your Database Title';"
```
5. **For rows not saving, check if you're using correct API endpoint and format** - see `README.md` for exact request structure.

---

### Issue 7: Authentication Issues (Can't Login or Session Expired)

**Symptoms:** Getting "Authentication required" error message when accessing app endpoints.

**Root Cause:** Flask session expired or invalid, email not matching database record.

**Solution Steps:**
1. **Clear browser cookies for localhost:**
   - Chrome: Settings → Privacy and Security → Clear Browsing Data → Cookies for all sites on this site only
2. **Try entering different email address** (session tokens are tied to user ID in database)
3. **Check if your original email exists in users table:**
   ```bash
   sqlite3 database.db "SELECT id, email FROM users;"
```
4. **If you changed Flask secret key or server restarted with different config**, session may be invalid - just login again with any valid email.
5. **For production deployment where sessions expire too quickly:** Increase `SESSION_TIMEOUT` value in app.py from 3600 to higher number (e.g., 86400 for 24 hours).

---

### Issue 8: "Database Locked" Error When Running App

**Symptoms:** Getting error like "database is locked" when trying to run `python backend/app.py`.

**Root Cause:** Another process (or previous instance of Flask app) still has the SQLite file open.

**Solution Steps:**
1. **On Linux/Mac, find and kill any processes using database.db:**
   ```bash
   lsof | grep database.db
```
2. **Kill those processes:**
   ```bash
   kill <PID>  # Replace with actual process IDs shown in previous command
```
3. **On Windows, use Task Manager or PowerShell to find and end any Python processes that might have left file open**.
4. **Or simply delete database.db and let app recreate fresh one:**
   ```bash
   rm database.db  # Backup first if you care about data!
cp backup_*.db database.db  # Restore from most recent backup if needed
```
5. **Ensure no other applications are reading/writing to the SQLite file** simultaneously.

---

### Issue 9: Slow Performance with Many Pages/Blocks

**Symptoms:** App feels sluggish, takes several seconds to render page list or blocks after creation.

**Root Cause:** Too many pages/blocks in single SQLite database causing query slowdowns and large file size.

**Solution Steps:**
1. **Keep pages under 50 blocks each for best UI performance** - split long documents into multiple shorter pages if needed
2. **Archive old content periodically by exporting to external storage or separate database**, then creating fresh SQLite file with only active data:
   ```bash
   # Backup current data first
cp database.db backup_before_archive.db
   
   # Delete and recreate empty database (you'll lose archived data - make sure it's backed up!)
rm database.db
python backend/init_db.py  # Recreate tables from scratch with fresh schema
```
3. **Consider migrating to PostgreSQL** if you need to store thousands of pages/blocks concurrently accessed by multiple users.
4. **Move cover images to external storage (S3/Cloudinary)** instead of storing as base64 BLOBs in SQLite - reduces database file size significantly.
5. **Add index on frequently queried columns:**
   ```bash
   sqlite3 database.db "CREATE INDEX IF NOT EXISTS idx_pages_updated ON pages(updated_at);"
```

---

### Issue 10: CORS Errors When Making API Calls from Browser Console

**Symptoms:** Getting `CORS policy blocked` or similar errors when trying to fetch data via browser console.

**Root Cause:** Flask-CORS configured to allow all origins in development mode, but some browsers block requests anyway if not properly set up.

**Solution Steps:**
1. **Verify CORS is enabled correctly in app.py - check line ~29:
   ```python
   from flask_cors import CORS
   CORS(app)  # This enables CORS for all routes with default allow-all origins (OK for development)
```
2. **For production, restrict to specific domains:**
   ```python
   CORS(app, resources={"r/*": {"origins":"https://yourdomain.com"}})
   ```
3. **Or disable browser's strict CORS checking in DevTools (Chrome only):** Settings → Privacy and Security → Site Settings → Cookies and site data → Allow cookies and site data
4. **Alternative: Use `fetch` with credentials flag disabled for cross-origin requests during development**:
   ```javascript
   fetch('/api/users/YOUR_USER_ID/pages', {mode:'no-cors'})
```
5. **For local testing, consider running backend on different port than browser proxy (e.g., Flask on 3000, Nginx reverse proxying to it)**.

---

## Advanced Debugging Techniques

### Check Database Schema Directly:
```bash
sqlite3 database.db ".schema"
```
Shows all table definitions and their current state - useful for verifying if new features were added correctly.

### View Current Session Data (via SQLite CLI):
```bash
# Note: Flask sessions are stored in cookies, not directly accessible via SQL queries
# But you can check which user is logged in by checking session cookie:
curl -I http://localhost:5000/api/users/YOUR_USER_ID/pages | grep "Set-Cookie"
```

### Test API Endpoints Directly with curl (bypass browser):
```bash
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "name": "Test User"}' | python -m json.tool
```
Should return JSON with `userId` and `success: true`. If you get error, backend is not working properly.

### Inspect Network Requests in Browser DevTools:
1. Open DevTools (F12)
2. Go to "Network" tab
3. Perform action that's failing (e.g., create page via UI)
4. Look at failed requests - check response status code and body for error message from backend
5. Common issues: 401 Unauthorized means session invalid, 404 Not Found means wrong endpoint URL, 500 Internal Server Error means Python exception occurred (check console for traceback).

---

## Prevention Tips to Avoid Future Issues:

### Before Making Major Changes:
```bash
# Always backup your database before experimenting with schema changes or migrations!
cp database.db backup_before_$(date +%Y%m%d_%H%M%S).db
```

### When Testing New Features Locally:
- Keep a fresh development instance separate from production data if possible
- Use environment variables to switch between test and prod databases (`DATABASE_PATH`)

### For Production Deployments:\n1. Set `DEBUG=false` in app.py or via environment variable (prevents detailed error messages leaking to users)
2. Enable HTTPS/TLS with reverse proxy (Nginx + SSL certificates) for secure connections
3. Implement rate limiting on API endpoints (`pip install Flask-Limiter`) to prevent abuse
4. Regular database backups and monitoring setup before going live!
5. Document all configuration changes so you can revert if needed.

---

## Still Having Issues?

### Check These Resources:
1. **README.md** - Full documentation with API reference and troubleshooting section
2. **FAQ.md** - Answers common questions you might have
3. **SUPPORT.md** - Detailed support options and getting help guides
4. **ARCHITECTURE.md** - Deep dive into technical implementation for advanced debugging
5. **CHANGELOG.md** - Version history with known issues from different releases
6. Open an issue on GitHub repository (if applicable) or email maintainer directly.

---

## Emergency Recovery Procedures:

### If You Accidentally Delete Your Database File:
1. Check for any backup files you created earlier (`backup_*.db`)
2. Look in system restore points (Windows) or Time Machine backups (Mac) if applicable
3. Try SQLite recovery tools like `.recover` command: `sqlite3 database.db ".recover"`
4. If using cloud storage with version history, may be able to restore previous versions there.
5. Consider rebuilding from scratch - your data was stored in pages/blocks tables which can be recreated via API calls if you have the content handy!

---

**Remember:** The SQLite database file (`database.db`) is where all your content lives. Any issues with it should be addressed immediately by backing up or recovering before proceeding.
