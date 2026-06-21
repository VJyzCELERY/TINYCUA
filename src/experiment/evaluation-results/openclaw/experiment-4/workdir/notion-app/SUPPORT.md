# 📞 Support & Getting Help - Notion Clone

## How to Get Help

### For Users (End-to-End Experience):
1. **Check the documentation files first:**
   - `START_HERE.md` - Quick intro for new users
   - `SETUP.md` - Detailed setup instructions  
   - `README.md` - Full features & API reference
   - `Instruction.md` - Simple usage guide
   - `FAQ.md` - Frequently asked questions

2. **Browser console (F12) is your friend:**
   ```javascript
   // Check if logged in:
   localStorage.getItem('user_email')
   
   // View API responses for debugging:
   fetch('/api/users/YOUR_USER_ID/pages').then(r => r.json())
     .then(d => console.log(JSON.stringify(d, null, 2)))
   ```

3. **SQLite inspection (if needed):**
   - Download [DB Browser for SQLite](https://sqlitebrowser.org/)
   - Open `database.db` file from project directory
   - Browse tables and verify data exists after operations

---

## Reporting Issues / Bugs

### Before Creating an Issue:
1. Check existing issues in repository (if on GitHub)
2. Review troubleshooting sections in README.md
3. Try restarting the Flask app (`Ctrl+C` then `python backend/app.py` again)
4. Clear browser cache and try again
5. Verify Python dependencies are installed: 
   ```bash
   pip install -r requirements.txt --upgrade
   ```

### What to Include in Issue Report:
- Operating system (Windows/Mac/Linux) + version
- Browser name/version used for testing
- Steps to reproduce the issue clearly
- Any error messages shown in browser console (F12 → Console tab)
- Network tab screenshots if API-related issues
- Current database contents (`sqlite3 database.db ".tables"`)

---

## Common Issues & Solutions

### Issue: "Module not found" / Import Error
**Solution:** Install dependencies:
```bash
pip install flask flask-cors click python-dotenv --upgrade
```
Or use requirements file:
```bash
pip install -r requirements.txt
```

---

### Issue: Port 5000 Already in Use
**Symptoms:** Error message when running `python backend/app.py` says port is already occupied.

**Solutions:**
1. Find and stop whatever's using that port:
   ```bash
   # Linux/Mac:
lsof -i :5000 | grep LISTEN
   kill <PID>
   
   # Windows (PowerShell):
   netstat -ano | findstr :5000
taskkill /PID <PID> /F
```
2. Or change port in `backend/app.py` line ~348:
   ```python
   app.run(debug=True, host='0.0.0.0', port=8000)  # Use different port
   ```

---

### Issue: Page Not Appearing After Creation
**Troubleshooting Steps:**
1. Check browser console for JavaScript errors (F12 → Console)
2. Verify API call succeeded:
   - Open Network tab in DevTools
   - Look at request to `/api/users/{id}/pages` endpoint
   - Confirm response includes valid `pageId`
3. Query database directly:
   ```bash
   sqlite3 database.db "SELECT * FROM pages;"
   # Should show your newly created page
```
4. If data exists but not showing: Refresh browser, clear cache, reload
5. Check if you're clicking the right sidebar item (verify title matches)

---

### Issue: Content Not Saving / Appearing Immediately
**Possible Causes:**
1. **Browser rendering lag**: Click away then back to trigger re-render
2. **Database write delay**: SQLite is synchronous, but UI may not update instantly
3. **Network latency**: If running remotely (not local development)
4. **Block creation failed**: Check console for API errors

**Solutions:**
- Try clicking outside the editor area to force re-render
- Or refresh page after adding content (data is still saved!)
- Verify database contains blocks: `sqlite3 database.db "SELECT * FROM blocks;"`

---

### Issue: Cover Images Not Displaying
**If using base64 encoding:**
1. Ensure image file size < 5MB recommended
2. Check MIME type is correct in response (should be `image/png` or similar)
3. Verify Base64 string includes proper data URI prefix (`data:image/...;base64,`)
4. If using browser console approach:
   ```javascript
   // Get image as base64 first:
   const canvas = document.createElement('canvas');
   canvas.width = 1200;
   canvas.height = 350;
   const ctx = canvas.getContext('2d');
   
   fetch('https://via.placeholder.com/1200x350') // Replace with your image
     .then(r => r.blob())
     .then(b => {
       const reader = new FileReader();
       reader.readAsDataURL(b);
       reader.onloadend = () => console.log(reader.result);  // Use this!
     });
   ```
5. Check CSS has cover image container: `.cover-image-container` styles

---

## Database Troubleshooting

### View Current State:
```bash
sqlite3 database.db ".tables"
# Shows all tables in current SQLite file

sqlite3 database.db "SELECT * FROM pages;"  # List all pages
sqlite3 database.db "SELECT COUNT(*) as blocks FROM blocks;"  # Total block count
```

### Check for Orphaned Data:
```bash
sqlite3 database.db ".schema"
# Review table schemas if structure changed unexpectedly
```

---

## Performance Issues / Slow Loading

If the app feels sluggish with many pages/blocks:

1. **Database file too large:** Consider archiving old content to separate DB
2. **Too many blocks per page**: Keep under 50 for best UI performance
3. **Large cover images stored as BLOBs**: Migrate to external storage (S3/Cloudinary)
4. **Browser memory usage high**: Clear cache, close other tabs

**Optimization Tips:**
- Archive less-used pages periodically by exporting and creating new database
- Use pagination in sidebar if >100 root-level pages exist
- Implement search/filter instead of showing all pages at once
- Migrate from SQLite BLOB to external image storage for large apps

---

## Security Concerns / Best Practices

### Current Implementation is Safe For:
✅ Local development and personal use  
✅ Single-user applications with email-only auth  
✅ Small datasets (<10K pages/blocks combined)  
✅ Learning Flask backend development  

### NOT Recommended For Production Without Improvements:
⚠️ Multi-user sharing (add proper authentication system first)
⚠️ Large-scale deployment (>50 users concurrently accessing same DB file)
⚠️ Storing sensitive user data without encryption/HTTPS
⚠️ Commercial applications requiring enterprise-grade security controls

### Production Security Checklist:
- [ ] Use HTTPS/TLS (reverse proxy with SSL certificates)
- [ ] Enable rate limiting on API endpoints (`pip install Flask-Limiter`)
- [ ] Restrict CORS origins to specific domains only
- [ ] Implement password hashing if adding passwords
- [ ] Set up proper error tracking and monitoring
- [ ] Regular database backups and recovery testing
- [ ] Input sanitization for all user-generated content (XSS prevention)
- [ ] SQL injection protection (already using parameterized queries! ✅)

---

## Migration & Upgrading Path

### From SQLite to PostgreSQL:
1. Install psycopg2: `pip install psycopg2-binary`
2. Modify connection string in app.py or use env var for DATABASE_URL
3. Use pgloader tool (https://github.com/dimitri/pgloader) OR custom migration script
4. Test thoroughly before migrating production data
5. Consider PostgreSQL only if you need multi-user concurrent access or plan to scale beyond SQLite limits

### Adding New Features:
See `CONTRIBUTING.md` for guidelines on adding new block types, features, or API endpoints.

---

## Requesting Feature Enhancements

If you'd like a feature added (like code blocks, dark mode, etc.):
1. Check if it's already in roadmap (`CHANGELOG.md`) 
2. Open an issue describing your use case and desired behavior
3. If possible, contribute the implementation yourself!
4. Be specific about:
   - What problem you're trying to solve
   - How this feature would work (UI/UX preferences)
   - Any relevant examples from other apps

---

## Contributing Fixes & Improvements

Want to fix a bug or add a feature?
1. Fork the repository on GitHub
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes following code style guide (`CONTRIBUTING.md`)
4. Test thoroughly in local environment first
5. Commit with clear messages describing what changed and why
6. Push to branch and create pull request
7. Describe what problem you solved or enhancement you made
8. Link related issue if applicable (e.g., "Fixes #123")
9. Wait for review - be responsive to feedback!

---

## Community Resources

### For Users:
- Browse open-source Notion alternatives: https://www.notion.so/help/alternatives
- Productivity tips and workflows using block-based editors online

### For Developers:
- Flask documentation: https://flask.palletsprojects.com/
- SQLite Python docs: https://docs.python.org/library/sqlite3.html  
- Vanilla JavaScript examples for contenteditable: MDN Web Docs
- CSS Grid/Flexbox tutorials for layout inspiration

---

## Getting in Touch

### For General Questions:
1. Review existing documentation files first (`README.md`, `FAQ.md`)
2. Check browser console (F12) for error messages
3. Query database directly with SQLite CLI if needed
4. Open an issue on GitHub repository for bug reports or feature requests
5. Or email the maintainer(s) privately for non-public inquiries

### For Business/Enterprise Use:
If you want to deploy this commercially, need custom features, or integrate into larger system:
- Consider reaching out directly about licensing options beyond MIT
- Discuss enterprise support agreements if needed
- Custom implementation requirements can be addressed via email

---

## Emergency Contacts (In Case of Data Loss)

### If You Accidentally Delete All Your Data:
1. **Check for backups**: Look for `backup_*.db` files in project directory  
2. **System restore points** (Windows) or Time Machine (Mac) may have previous versions
3. **Version control history** if you had git committed before accident
4. **SQLite recovery tools**: Use `.recover` command in sqlite3 CLI to attempt data extraction
5. **Cloud backup services** if database was synced via Dropbox/Google Drive/etc.

### Prevention:
- Regularly back up `database.db` file (copy to external storage)
- Consider using version control for code, not SQLite files themselves  
- Implement automated backups in production deployments
- Document your data export/import procedures before starting with this app

---

**Still need help?** Open an issue on GitHub or email the maintainer directly!
