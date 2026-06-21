# 🧪 Testing Guide - Notion Clone

## Automated Tests (Future Enhancement)

Currently, the app is tested manually via browser. Here's how to add automated tests:

### 1. Install pytest and Flask Test Client
```bash
pip install pytest pytest-flask requests beautifulsoup4
```

### 2. Create test file: `backend/test_app.py` (Example):

```python
import unittest
from app import app, init_db

class TestPageCreation(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = app.test_client()
        
        # Mock session for authentication
        with self.client.session as sess:
            sess['user_id'] = 1
            sess['email'] = 'test@example.com'
    
    def test_create_page(self):
        response = self.client.post('/api/users/1/pages',
                                   data=json.dumps({'title': 'Test Page'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 201)
        json_response = response.get_json()
        self.assertIn('pageId', json_response)
    
    def test_get_pages(self):
        response = self.client.get('/api/users/1/pages')
        self.assertEqual(response.status_code, 200)
```

---

## Manual Testing Checklist

### Basic Functionality:
- [ ] Can create new pages via "+ New Page" button
- [ ] Pages appear in sidebar with correct titles
- [ ] Clicking sidebar page navigates to that page
- [ ] Content is editable (click any text, type)
- [ ] Press Enter creates new blocks/paragraphs
- [ ] Headings display correctly (H1, H2, H3)
- [ ] Lists render properly (bullet and numbered)
- [ ] Blockquotes work with Tab key or manual input
- 
### Authentication:
- [ ] Can enter email and login successfully
- [ ] Session persists across page reloads
- [ ] Different emails create separate user data

### API Testing (using curl/Postman):
```
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "name": "Test User"}'

# Get pages (you'll need to parse response for user_id)
curl http://localhost:5000/api/users/YOUR_USER_ID/pages
```

### Edge Cases:
- [ ] Creating page with empty title shows default
- [ ] Very long titles are truncated in sidebar display
- [ ] Special characters (quotes, ampersands) don't break HTML
- [ ] Database tables handle duplicate row data gracefully
- 
---

## Browser Console Testing Commands

### Test Authentication:
```javascript
// Check if logged in
console.log('User ID:', localStorage.getItem('user_id'));
```

### View API Response Structure:
```javascript
fetch('/api/users/YOUR_USER_ID/pages')
  .then(r => r.json())
  .then(data => console.log(JSON.stringify(data, null, 2)))
```

---

## Performance Testing (Optional)

### Load Test with Apache Bench:
```bash
ab -n 100 -c 10 http://localhost:5000/api/users/USER_ID/pages
```

Expected results for development setup:
- Page list GET: ~200ms response time
- Block creation POST: ~300ms with SQLite write

### Memory Usage Check (Python):
```python
import tracemalloc
tracemalloc.start()
# Run app operations here...
current, peak = tracemalloc.get_traced_memory()
print(f'Current memory usage: {current / 10**6:.2f} MB')
```

---

## Database Testing Queries (SQLite)

### View all pages:
```bash
sqlite3 database.db "SELECT * FROM pages;"
```

### Check block count per page:
```sql
SELECT p.title, COUNT(b.id) as blocks 
FROM pages p LEFT JOIN blocks b ON p.id = b.page_id 
GROUP BY p.id;
```

### Verify user sessions aren't shared (security check):
```bash
sqlite3 database.db "SELECT email FROM users;"
# Each session should have different effective data
```

---

## Security Testing Checklist

- [ ] No SQL injection via API parameters (parameterized queries used)
- [ ] CORS headers don't allow all origins in production mode
- [ ] Session tokens expire after timeout period
- [ ] XSS prevention: HTML entities escaped before rendering
- [ ] File upload validation if implemented later

### Test for SQL Injection:
```bash
curl -X POST http://localhost:5000/api/users/1/pages \
  -H "Content-Type: application/json" \
  -d '{"title": "test' OR '1'=1 --", "icon": "📝"}'
# Should fail safely, not execute malicious query
```

---

## Continuous Integration Setup (Optional)

### GitHub Actions Example:
Create `.github/workflows/test.yml`:
```yaml
name: Test Suite
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install flask flask-cors pytest
      - name: Run tests
        run: cd backend && pytest test_app.py --verbose
```

---

## Known Issues to Watch For

| Issue | Status |
|-------|--------|
| Cover images not displaying in UI (base64 encoding) | ⚠️ Needs frontend fix |
| Database tables API endpoint needs clarification | 📝 Documentation update needed |
| No error handling for malformed JSON requests | 🔧 Add try/except blocks |

---

## Test Report Template

```
Test Run: YYYY-MM-DD HH:MM:SS
Environment: Local Development (Python 3.x, Flask 3.0)
Browser Tested On:
- [ ] Chrome
- [ ] Firefox
- [ ] Safari
- [ ] Edge

Results Summary:
✅ Passed: X tests
❌ Failed: Y tests (see below)
⚠️ Warnings: Z items

Failure Details:
1. Test name - Description of failure
2. Stack trace or error message
3. Steps to reproduce

Next Actions:
- Fix failing tests
- Update documentation for known issues
```
