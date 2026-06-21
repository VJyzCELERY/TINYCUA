# 📝 Notion Clone - Python Flask App

<div align="center">
  <h3>A lightweight, intuitive web app inspired by Notion using Python Flask and SQLite</h3>
  
  ![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
  ![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
  ![SQLite](https://img.shields.io/badge/SQLite-local--first-blue.svg)
</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📝 **Rich Text Editing** | Block-based structure with headings, paragraphs, lists, quotes |
| 🔖 **Cover Images** | Add background images to any page (via base64 encoding) |
| 🏷️ **Emoji Icons** | Visual organization on pages like Notion does |
| 💾 **SQLite Storage** | Local-first persistence - everything saved automatically |
| 👤 **Simple Auth** | Email-based login, no password needed for local use! |
| 🗂️ **Page Organization** | Sidebar navigation between multiple documents |
| 📊 **Database Tables** | Create tables with columns and rows for organizing data |
| 🎨 **Clean UI** | Notion-inspired design and intuitive experience |

---

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies
```bash
cd /workspace/experiment-4/notion-app
pip install flask flask-cors click python-dotenv --upgrade
```

### Step 2: Run the Application
```bash
python backend/app.py
```
The app will start at **http://localhost:5000**.

### Step 3: Open in Browser
1. Go to http://localhost:5000
2. Enter any email (e.g., `hello@example.com`)
3. Click "Continue" - you're logged in!
4. Create your first page by clicking "+ New Page"
5. Start typing, add headings, lists, and more!

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| **START_HERE.md** | Quick intro for new users - start here! |
| **SETUP.md** | Detailed setup instructions with troubleshooting |
| **Instruction.md** | Simple usage guide for beginners |
| **QUICK_START.md** | 2-minute quick start to get running |
| **FAQ.md** | Frequently asked questions and answers |
| **FEATURES.md** | Complete features overview and roadmap ideas |
| **TROUBLESHOOTING.md** | Common issues and solutions |
| **GETTING_STARTED.md** | Step-by-step guide from first run |

### For Developers:
- **ARCHITECTURE.md** - Technical deep dive into implementation
- **DEPLOYMENT.md** - Production deployment options and setup
- **CONTRIBUTING.md** - How to add new features yourself
- **TESTING.md** - Testing guidelines and checklists
- **NOTICE.md** - License, legal notice, and attribution info
- **CHANGELOG.md** - Version history and future roadmap ideas

### Additional Resources:
- **BACKUP_README.md** - Backup/restore procedures for SQLite database
- **SUPPORT.md** - How to get help when needed
- **PROJECT_SUMMARY.md** - Summary of the entire project
- **NOTES.md** - Tips, tricks, and developer notes

---

## 🛠️ Project Structure

```
notion-app/
├── backend/                    # Python Flask application
│   ├── app.py                 ← Main application (run this!)
│   └── init_db.py             ← Database initialization script
├── frontend/public/            # Static files for browser
│   ├── index.html              → Entry point
│   ├── css/style_enhanced.css  → All styling (Notion-inspired design)
│   └── js/
│       ├── app_enhanced.js     → Main frontend logic (editing, navigation)
│       └── auth.js             ← Login handling and session management
├── requirements.txt            ← Python dependencies
└── *.md                       ← Comprehensive documentation files:
    ├── START_HERE.md          ← Quick intro for new users
    ├── SETUP.md               ← Detailed setup instructions
    ├── README.md              ← This file!
    ├── Instruction.md         ← Simple usage guide for beginners
    ├── QUICK_START.md         ← 2-minute quick start to get running
    ├── FAQ.md                 ← Frequently asked questions and answers
    ├── FEATURES.md            ← Complete features overview and roadmap ideas
    ├── TROUBLESHOOTING.md     ← Common issues and solutions
    ├── GETTING_STARTED.md     ← Step-by-step guide from first run
    ├── ARCHITECTURE.md        ← Technical deep dive into implementation
    ├── DEPLOYMENT.md          ← Production deployment options and setup
    ├── CONTRIBUTING.md        ← How to add new features yourself
    ├── TESTING.md             ← Testing guidelines and checklists
    ├── NOTICE.md              ← License, legal notice, attribution info
    ├── CHANGELOG.md           ← Version history and future roadmap ideas
    └── BACKUP_README.md       ← Backup/restore procedures for SQLite database
```

---

## 🎯 What You Get

### Core Functionality:
- **Rich text editing** with block-based structure (headings, paragraphs, lists)
- **Page organization system** with sidebar navigation between documents
- **Cover images support** via base64 encoding or external storage migration
- **Database tables** for organizing content in table format
- **Email authentication** - simple login without password required!
- **Local-first persistence** using SQLite database (auto-saves everything)
- **Clean UI design** inspired by Notion's intuitive interface

### API Endpoints:
The app exposes a clean RESTful JSON API for integration with other tools:
- `POST /api/login` - Email-based authentication
- `GET/POST /api/users/{id}/pages` - Page CRUD operations
- `PUT /api/users/{id}/pages/{page_id}` - Update page metadata
- `POST /api/users/{id}/pages/<page_id>/blocks` - Add block to page
- And more... (see README.md for full API reference)

---

## 🎓 Learning Goals This Project Teaches:

This project is perfect for learning:
1. **Flask backend development** - RESTful APIs, session management, routing
2. **SQLite database design** - Schema planning, relationships, JSON storage
3. **Vanilla JavaScript frontend** - ContentEditable API, DOM manipulation without frameworks
4. **Full-stack architecture** - Connecting Python backend to browser via HTTP/JSON
5. **Local-first app development** - Self-contained applications with SQLite persistence

---

## 📖 Quick Tutorial: Create Your First Page (30 Seconds)

1. Run the app: `python backend/app.py`
2. Open http://localhost:5000 in browser
3. Enter email → Click "Continue"
4. Look at left sidebar, click "+ New Page" button
5. Type a title when prompted (e.g., "My Notes")
6. ✨ Done! Start typing content - everything auto-saves!

---

## 💡 Tips for Using the App

### Creating Content:
- **Headings:** Type `# Title` or use block type `{"type":"h1","content":"Title"}` in API calls
- **Paragraphs:** Just start typing - press Enter for new blocks/paragraphs
- **Lists:** Use `- item 1`, Enter, then `- item 2` for bullet points; `1. First`, Enter, then `2. Second` for numbered lists
- **Quotes:** Select text and hit Tab to get `>` prefix (blockquote)

### Organizing Your Workspace:
- Click "+ New Page" in sidebar to create new pages
- Use emoji icons like 📝, 🗂️, 💡 to visually distinguish different types of content
- Create multiple documents instead of one giant file for better organization

### Adding Cover Images (Optional):
Use browser console after loading a page:
```javascript
fetch('/api/users/YOUR_USER_ID/pages/' + PAGE_ID, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({coverImage: "data:image/png;base64,...YOUR_BASE64_IMAGE..."})
});
To get base64 from an image:
1. Convert your image to base64 online (https://www.base64-image.de/)
2. Or use browser console directly with fetch and blob conversion
```

### Creating Database Tables:
1. Create a new page with title like "📊 My Projects"
2. Add columns as headings: `# Name`, `# Status`, `# Priority`
The table structure is stored automatically in SQLite!

---

## 🔒 Security Notes (Current Implementation)

### Safe For:
✅ Local development and personal use  
✅ Single-user applications with email-only authentication  
✅ Small datasets (<10K pages/blocks combined)  
✅ Learning Flask backend development  

### Not Recommended For Production Without Improvements:
⚠️ Multi-user sharing (add proper authentication system first)  
⚠️ Large-scale deployment (>50 users accessing same DB file)  
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

## 🚀 Deployment Options

### Local Development (Current State):
The app is designed to run locally on your machine:
```bash
python backend/app.py  # Runs on localhost:5000
```

### Production Deployment:
See `DEPLOYMENT.md` for detailed instructions covering:
- Self-hosted deployment with Gunicorn + Nginx
- Cloud platforms (Railway, Render, Heroku)
- Docker containerization options
- Database migration to PostgreSQL for scaling
- SSL/HTTPS setup and security hardening

---

## 🧪 Testing & Development

### Manual Testing:
The app is tested manually via browser. Here's how to add automated tests:
1. Install pytest: `pip install pytest flask-flask-cors`
2. Create test file in `backend/test_app.py` (see TESTING.md for examples)
3. Run tests with: `pytest backend/ -v`

### Database Inspection Tools:
- Download [DB Browser for SQLite](https://sqlitebrowser.org/) to browse your database visually
- Use SQLite CLI commands: `sqlite3 database.db ".tables"` or `.schema`

---

## 📝 License & Attribution

This project is released under the **MIT License** - feel free to use, modify, and distribute!

Give credit where due:
```
Notion Clone © 2026 | Built with Flask + SQLite
Inspired by Notion's block-based editing approach.
```

---

## 🤝 Contributing & Roadmap Ideas

### Current Limitations (v1.0):
- No real-time collaboration features
- Images stored as base64 BLOBs in SQLite (not scalable for large apps)
- Single-user design with email-only authentication
- Limited block types compared to full Notion

### Future Enhancement Ideas:
1. **Code Blocks** with syntax highlighting (`type: 'code'` support)
2. **Toggle Lists** for collapsible sections
3. **Callout/Tip Boxes** (like Notion's quote blocks for tips)
4. **Rich Text Toolbar** (bold, italic, underline buttons via toolbar UI)
5. **File Uploads** to external storage like S3/Cloudinary instead of SQLite BLOBs
6. **Dark Mode Toggle** with CSS variables and theming support
7. **Markdown Support** - automatically parse markdown input into blocks (`# Title` → h1 block)
8. **Search/Filter Pages** by title or content across all pages
9. **Export Functionality** as PDF/MHTML for sharing offline copies
10. **Real-time Sync** using WebSockets (Socket.io) for collaboration features

---

## ❓ Getting Help & Support

### Before Creating an Issue:
1. Check existing documentation files first (`README.md`, `FAQ.md`)
2. Review troubleshooting section in TROUBLESHOOTING.md
3. Try restarting the Flask app (Ctrl+C then run again)
4. Clear browser cache and try again
5. Verify Python dependencies are installed: `pip install -r requirements.txt --upgrade`

### For Users:
- **Browser console** is your friend! Open DevTools with F12 to inspect API responses
- **SQLite inspection**: Download DB Browser for SQLite or use CLI commands directly
- **Check database contents**: `sqlite3 database.db "SELECT * FROM pages;"` shows all created pages

### For Developers:
- See CONTRIBUTING.md guidelines and code style recommendations
- Review ARCHITECTURE.md for deeper technical understanding
- Check TESTING.md before adding new features or fixing bugs

---

## 🎯 Summary: Why Build This?

This project demonstrates how to build a productivity app from scratch using:
- **Minimal dependencies** (Flask only, no React/Vue/Angular)
- **Local-first storage** (SQLite, everything saved locally on your machine)
- **Simple authentication model** (email-only for local use)
- **Clean API design** (RESTful endpoints with JSON responses)

It's perfect for:
- Learning Flask backend development ✅
- Understanding database schema design ✅
- Building intuitive UIs without frameworks ✅
- Creating your own "second brain" workspace 💡

Whether you want to use it as-is or extend it further, the foundation is solid and extensible!

---

<div align="center">
  <h3>Happy building! 🎉</h3>
  <p>Built with ❤️ using Python Flask + SQLite for local-first productivity.</p>
</div>
