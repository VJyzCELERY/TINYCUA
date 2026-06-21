import { useEffect, useState } from 'react';
import axios from 'axios';
import './Home.css';

export default function Home() {
  const [recentPages, setRecentPages] = useState([]);

  // Fetch recent pages on mount (would use localStorage in real app)
  useEffect(() => {
    fetchRecent();
    
    // Simulate fetching from API or localStorage
    const saved = JSON.parse(localStorage.getItem('notion_pages') || '[]');
    if (saved.length > 0) {
      setRecentPages(saved.slice(0, 5));
    } else {
      createWelcomePage();
    };

    const fetchRecent = async () => {
      try {
        console.log('Would fetch recent pages from API');
        
        // For demo, use localStorage or create default page
        setRecentPages([
          { id: 'demo-1', title: 'Welcome to NoteSpace!', icon_data: '📝' },
          { id: 'demo-2', title: 'Untitled Page 1', icon_data: '' },
          { id: 'demo-3', title: 'Project Ideas', icon_data: '💡' }
        ]);
      } catch (error) {
        console.error('Error fetching pages:', error);
      }
    };

    const createWelcomePage = async () => {
      try {
        await axios.post('/api/pages', { title: 'Welcome to NoteSpace!', properties: {} });
        
        if (!recentPages.find(p => p.title === 'Welcome to NoteSpace!')) {
          setRecentPages([recentPages[0]]);
        }
      } catch (error) {
        if (error.response?.status === 409) {
          setRecentPages([recentPages[0]]);
        } else {
          throw error;
        }
      }
    };

    return () => {};
  }, []);

  const handleCreatePage = async (title) => {
    try {
      await axios.post('/api/pages', { title });
      
      if (!recentPages.find(p => p.title === 'Welcome to NoteSpace!')) {
        setRecentPages([
          ...recentPages,
          { id: `page-${Date.now()}`, title }
        ]);
      }
    } catch (error) {
      console.error('Error creating page:', error);
    }
  };

  return (
    <div className="home-page">
      {!recentPages.length && (
        <div className="empty-state">
          <h2>Welcome to NoteSpace!</h2>
          <p>Your pages will appear here</p>
          
          <button 
            onClick={() => handleCreatePage('New Page')}
            className="btn-create-page"
          >
            Create your first page
          </button>
        </div>
      )}

      {recentPages.length > 0 && (
        <div className="pages-list">
          <h3>Your pages</h3>
          
          {recentPages.map((page) => (
            <Link 
              key={page.id}
              to={`/page/${page.id}`}
              onClick={(e) => e.preventDefault()}
              className="page-item"
            >
              <div className="page-icon">{page.icon_data || '📄'}</div>
              <span className={`title-${Math.floor(Math.random() * 5) + 1}`}>
                {page.title}
              </span>
            </Link>
          ))}

          <button 
            onClick={() => handleCreatePage('New Page')}
            className="btn-new-page-home"
            title="Create new page"
          >
            + New page
          </button>
        </div>
      )}
    </div>
  );
}
