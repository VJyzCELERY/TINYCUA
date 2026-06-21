# ⚡ Quick Start - Get Running in 2 Minutes!

## Prerequisites Check

Make sure you have:
- ✅ Python 3.8+ installed (`python --version`)
- ✅ pip package manager available (`pip --version`)
- ✅ A web browser (Chrome, Firefox, Safari recommended)

---

## Step-by-Step Installation

### Step 1: Navigate to the Project
```bash
cd /workspace/experiment-4/notion-app
```

### Step 2: Install Python Dependencies
```bash
pip install flask flask-cors click python-dotenv
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

Expected output:
```
✓ Database initialized successfully!
 * Running on http://0.0.0.0:5000
Press CTRL+C to quit
```

---

## Access Your App

1. Open your browser
2. Go to **http://localhost:5000**  
3. Enter any email (e.g., `hello@example.com`)
4. Click "Continue" button
5. ✨ You're ready!

---

## Your First Page - In 10 Seconds

### Create Page:
1. Look at the left sidebar
2. Click "+ New Page"
3. Type a title when prompted (e.g., "My Notes")
4. ✨ Done!

### Add Content:
- Just start typing in the editor area
- Press Enter for new paragraphs/blocks
- Select text and hit Tab for quotes (>)
- Use H1, H2, or H3 to create headings

---

## What You Can Do Now 🎉

| Action | Result |
|--------|-------|
| Click sidebar page name | Switches between pages |
| Click "+ New Page" | Creates new blank page |
| Type in editor area | Content auto-saves to SQLite |
| Add headings (# Title) | Creates H1/H2/H3 blocks |
| Use bullet points (- item) | Creates unordered lists |

---

## Troubleshooting Quick Fixes

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

## Next Steps After Getting Started

1. **Read Instruction.md** - Learn all features and tips
2. **Check README.md** - See API reference and advanced usage
3. **Explore the sidebar** - Create multiple pages, organize your workspace
4. **Try adding cover images** (via browser console for fun!)
5. **Create database tables** by making heading-based columns

---

## That's It! 

You now have a Notion-like app running locally with:
- Full rich text editing ✍️
- Page organization 📑  
- SQLite persistence 💾
- Clean, intuitive UI 🎨

Enjoy building your second brain!
🚀

---

## Additional Resources

- **Architecture**: `ARCHITECTURE.md` - Deep dive into how it works  
- **Contributing**: `CONTRIBUTING.md` - Add new features yourself  
- **Changelog**: `CHANGELOG.md` - Version history and roadmap ideas  
- **Troubleshooting**: Read the troubleshooting section in README.md

---

## Keyboard Shortcuts Reference

| Key | Action |
|-----|--------|
| Enter | New paragraph/block |
| Tab | Add quote (>) prefix |
| Shift+Enter | Line break within same block |
| Ctrl+C/V | Copy/paste works! |
| Delete/Backspace | Remove characters like any text editor |

---

**Happy building!** 🎨✨
