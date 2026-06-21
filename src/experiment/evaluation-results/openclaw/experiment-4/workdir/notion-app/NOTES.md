# 💡 Notes & Tips for Using Notion Clone

## Quick Reference Guide

### Creating Content Types

| Action | How to Do It |
|--------|-------------|
| **Add Heading** | Type `# Title` or use block type: `{"type":"h1","content":"Title"}` |
| **Add Paragraph** | Just start typing - it's a paragraph by default! |
| **Unordered List** | Type `- item 1`, press Enter, then `- item 2` |
| **Ordered List** | Type `1. First`, press Enter, then `2. Second` |
| **Blockquote** | Select text and hit Tab to get ">" prefix |
| **Cover Image** | Via API or browser console (see README.md) |

### Keyboard Shortcuts Tips
- `Enter` - Create new block/paragraph  
- `Tab` - Add quote/blockquote character  
- `Shift+Enter` - Line break within paragraph  
- `Ctrl+S` - Not needed! Everything auto-saves to SQLite  

---

## Browser Console Commands (Advanced Users)

### Set Cover Image for Current Page
```javascript
// Run in browser console (F12 → Console tab) after loading a page:
fetch('/api/users/YOUR_USER_ID/pages/' + PAGE_ID, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({coverImage: "data:image/png;base64,...YOUR_BASE64_IMAGE..."})
});
```

### Get Your User ID from Console
```javascript
// After logging in:
fetch('/api/users/YOUR_EMAIL/pages')
    .then(r => r.json())
    .then(d => console.log('Your pages:', d.pages));
```

---

## Database Table Usage

### Creating a Simple Table
1. Create a new page with title like "📊 My Projects"
2. Add columns as headings in the body:
   - `# Name` (H1 for column header)
   - `# Status` 
3. The table will appear when you add rows via API calls

### Adding Rows to Table
```javascript
document.getElementById('editor').dispatchEvent(new CustomEvent('add-row', {
    detail: {name: 'Project A', status: 'In Progress'}
}));
```

---

## Database Schema (For Developers)

### Tables Created Automatically:

1. **users** - User authentication and profiles
2. **pages** - Main content pages with titles, icons, covers
3. **blocks** - Individual text blocks within pages
4. **database_tables** - Table entries for Notion-style databases
5. **database_columns** - Column definitions for database tables

### SQLite File Location:
- `notion-app/database.db` (auto-created on first run)

---

## Performance Tips

1. **Keep page titles concise** - Long titles make sidebar cluttered
2. **Use icons sparingly** - One emoji per page is enough  
3. **Don't create too many pages at once** - Browser may slow down with hundreds of pages
4. **Clear browser cache occasionally** if app feels sluggish

---

## Security Notes

### Current Implementation (Development Only)
- ⚠️ Session-based auth stored in cookies (no password hashing needed for local use)
- ⚠️ All data stored locally on your machine
- ✅ No external API calls to third parties
- ✅ Images encoded as base64 and stored in SQLite

### For Production Use:
Consider adding:
1. Password hashing with bcrypt/argon2
2. JWT tokens for session management
3. HTTPS/TLS encryption
4. Input sanitization (XSS prevention)
5. Rate limiting on API endpoints
6. CSRF protection headers
7. SQL injection prevention (already using parameterized queries!)

---

## Troubleshooting Checklist

### Page Not Showing?
- ✅ Check browser console for errors (F12 → Console)
- ✅ Try clearing browser cache and reload
- ✅ Verify you're on the right page in sidebar

### Content Not Saving?
- ✅ Open network tab (F12 → Network) - check if API calls succeed
- ✅ Look for 401/403 errors indicating auth issues
- ✅ Ensure email entered matches session token

### Database Tables Not Working?
- ✅ Make sure columns are added as headings first
- ✅ Check that table title is unique (no duplicates)

---

## Migration Notes

If upgrading from an older version:
1. Backup your `database.db` file before making changes
2. New versions may have different API endpoints
3. Frontend JavaScript files need to match backend versions
4. Database schema should be backward compatible (uses CREATE TABLE IF NOT EXISTS)

---

## Future Enhancement Ideas

### For Users Who Want More:
1. **Markdown Import** - Upload .md files and parse them into blocks
2. **Template Pages** - Create reusable page templates
3. **Page Templates Gallery** - Browse community-created layouts
4. **Import from Notion/Google Docs** - Migration tools
5. **Export to PDF/MHTML** for sharing offline copies
6. **Local Search** across all pages and blocks
7. **Tags/Categories** system for organizing content
8. **Favicons per page** (favicon.ico support)
9. **Page Templates** with predefined layouts
10. **Collaborative editing** via WebSockets in future versions
