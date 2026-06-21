# User Guide - Notion Clone Application

## First Time Setup 🎯

### 1. Install & Start the App

```bash
pip install -r requirements.txt
python app/init_db.py  
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open your browser and go to `http://localhost:8000`

---

## Interface Overview 🧭

### Sidebar (Left Panel)

The sidebar contains all navigation options:

| Icon | Action | Description |
|------|--------|-------------|
| 🔍 Search bar | Find pages or databases quickly by typing keywords |
| 👤 Personal Workspace | Your main workspace area |
| 📄 Pages list | Browse and select your existing pages |
| + New Page button | Create a fresh blank page instantly |
| 🗂️ Database button | Open modal to create new database/table |
| ⚙️ Settings | Configure current page (icon, cover image) |

### Main Content Area

This is where you work:

- **Cover Image**: Click the gradient bar at top of any page to add/change cover photo
- **Title Input**: Large text box for page title - click anywhere in editor and press Backspace if empty
- **Block Editor**: Monaco-based rich text editor (same as VS Code!)
  - Press `Enter` → New paragraph block below
  - Press `Backspace` on empty line → Delete current block  
  - Use toolbar buttons above editor for quick format options: H1, H2, Paragraph, Quote, Lists

### Page Sidebar (Right Panel)

Click the "⋯" button in header to open page sidebar with:
- Table of contents (auto-generated from headings)
- Bookmarks and links section  
- Page actions at bottom

---

## Creating Pages 📄

### Method 1: From Sidebar (+ Button)
1. Click **+ New Page** in sidebar footer
2. Enter title or leave blank for "Untitled" page
3. Choose icon (emoji grid appears when you click the emoji button)  
4. Click **Create Page** → Opens new page instantly

### Method 2: Duplicate Existing Page
1. Open any page's ⋯ menu in header
2. Select **"📋 Duplicate page"**
3. Edit title and content as needed

---

## Working with Blocks (Content) 🧱

The editor uses a **block-based editing system** like Notion:

### Adding Content

- Press `Enter` anywhere → Creates new paragraph block below current one  
- Click toolbar buttons above editor to insert different types
  - `<i class="fas fa-heading"></i>` = Heading 1 (large title)
  - `<i class="fab fa-hacker-news"></i>` = Heading 2 (subheading) 
  - `<i class="fas fa-paragraph"></i>` = Regular paragraph text
  - `<i class="fas fa-quote-left"></i>` = Blockquote with quote styling  
  - `<i class="fas fa-list-ul"></i>` = Bullet list item
  - `<i class="fas fa-list-ol"></i>` = Numbered list item

### Deleting Content

Click anywhere in a block, then press `Backspace` to delete it. The empty space disappears immediately (no "empty line" between blocks).

---

## Creating Databases 🗂️  

Databases are like tables with properties for organizing your pages as entries:

1. Click **Database** button in sidebar footer
2. Enter database title (e.g., "Tasks", "Projects", "Team Members")  
3. Choose icon from emoji picker or leave default table icon
4. Select column type for first property: Text, Number, Date, Checkbox, Select, Email

### Adding More Columns

Click the **+** button in database header to add new columns with different types. Each column becomes a sortable/filterable field.

### Adding Rows (Entries)

Click **+** in table header → Opens empty row where you can:
- Enter title for each entry  
- Select values from dropdowns (checkboxes, dates, selects)

---

## Page Settings ⚙️  

Open settings by clicking **⋯** button in page editor header or right sidebar.

### Cover Image
1. Click "Cover image" placeholder at top of any page
2. Choose photo file → Preview appears below upload input  
3. Drag edges to crop/resize (coming soon)

### Page Icon
Click emoji picker icon next to current icon:
- Browse 50+ emoji options in grid modal
- Select one or type custom Unicode character

### Description
Add page description text that shows up at top of sidebar when hovering over page item.

---

## Sharing Pages 🔗  

1. Click **Share** (share-alt) icon in header  
2. Copy generated link → Share via email, Slack, etc.
3. Configure who can access:
   - **Anyone with link**: View only / Comment / Full editing
   - **Specific people**: Enter emails to invite

---

## Comments 💬  

1. Click **Comment** (comment-dots) icon in header  
2. Type your comment → Click **"Add Comment"**  
3. See all comments threaded below each other

---

## Keyboard Shortcuts ⌨️

| Shortcut | Action |
|----------|--------|
| `Enter` | Create new block below current one |
| `Backspace` (on empty line) | Delete current block |
| `/` | Open command menu for inserting blocks (coming soon) |
| `Ctrl/Cmd + K` | Quick link search (like Notion's quick links, coming soon) |

---

## Best Practices 💡

### Organization Tips:
- Use **Databases** as your main organizational tool  
  - Create a "Tasks" database with Status/Priority columns
  - Create a "Projects" database linking to project documentation pages
  
- Name pages clearly and use meaningful icons (📄 for docs, 🚀 for projects, ⭐️ for favorites)

### Database Usage:
- Always add at least one column per property you want  
- Use **Select** columns with predefined options for consistency  
  - Example: Status = ["Not Started", "In Progress", "Done"]  

---

## Troubleshooting 🔧

| Issue | Solution |
|-------|----------|
| Page title not saving | Click outside the input box or press `Enter` to confirm |
| Can't add blocks | Make sure you're in edit mode (not viewing a database) |
| Database columns don't appear | Refresh browser page and reload data from API |
| Cover image doesn't upload | Check file size (< 10MB recommended), try different format |

---

## Coming Soon 🚀  

- `/` command menu for inserting blocks with keyboard  
- Slash commands (type `/` to insert headings, lists, quotes)  
- Real-time collaboration (see what others are editing live)
- Keyboard shortcuts like `Ctrl + A` (select all), `Ctrl + Z` (undo)  
- Database views: Board view (Kanban cards), Calendar view

---

For technical documentation and API reference, see:
- `/workspace/experiment-4/README.md` - Project overview  
- `/workspace/experiment-4/API_DOCS.md` - Full API specification  
