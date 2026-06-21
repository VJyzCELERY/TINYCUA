# 🚀 Setup Instructions for Notion Clone

## Quick Start (3 Steps)

### Step 1: Install Dependencies
```bash
cd /workspace/experiment-4/notion-app
pip install flask flask-cors click python-dotenv
```

### Step 2: Initialize Database (optional - done automatically on startup)
```bash
python backend/init_db.py
```

### Step 3: Run the Application
```bash
python backend/app.py
```

## Access Your App

Open your browser and navigate to:
**http://localhost:5000**

Enter any email (e.g., `hello@example.com`) - no password needed!

---

## What You Get

After setup, you have a fully functional Notion-like app with:

✅ **Rich Text Editing** - Headings, paragraphs, lists all supported  
✅ **Page Organization** - Sidebar navigation between pages  
✅ **Cover Images** - Add background images to any page  
✅ **Database Tables** - Create tables for organizing data  
✅ **Simple Auth** - Email-based login (no password!)  
✅ **SQLite Storage** - All your content saved locally  

---

## Project Files Explained

```
notion-app/
├── backend/              # Python Flask application
│   ├── app.py           ← Main application (run this!)
│   └── init_db.py       ← Database initialization script
├── frontend/public/      # Static files served by Flask
│   ├── index.html       → Entry point for browser
│   ├── css/
│   │   └── style_enhanced.css  → All styling
│   └── js/
│       ├── app_enhanced.js     → Frontend JavaScript
│       └── auth.js             → Authentication logic
├── requirements.txt      ← Python dependencies
├── README.md            ← Full documentation
├── Instruction.md       ← Simple usage guide
└── SETUP.md            ← This file!
```

---

## Troubleshooting

### "Module not found" error?
```bash
pip install -r requirements.txt --upgrade
```

### Port 5000 already in use?
Edit `backend/app.py` line ~348:
```python
app.run(debug=True, host='0.0.0.0', port=8000)  # Change to different port
```

---

## Next Steps

1. Open http://localhost:5000 in your browser
2. Enter an email and click "Continue"
3. Click "+ New Page" to create your first page!
4. Start building your workspace 🎉
