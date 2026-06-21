import { useState, useEffect } from 'react';
import { Link, useLocation, Outlet } from 'react-router-dom';
import './Layout.css';

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const location = useLocation();
  
  // Close sidebar on mobile when navigating
  useEffect(() => {
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    } else {
      setSidebarOpen(true);
    }
  }, [location]);

  return (
    <div className="app">
      {/* Sidebar */}
      <aside 
        className={`sidebar ${!sidebarOpen ? 'closed' : ''}`}
        style={{ display: sidebarOpen && window.innerWidth >= 768 ? 'block' : 'none' }}
      >
        <div className="sidebar-header">
          <h1>NoteSpace</h1>
        </div>

        {/* Quick Actions */}
        <nav className="quick-actions">
          <button onClick={() => window.location.href = '/api/pages'} className="btn-new-page" title="Create Page">
            + New Page
          </button>
        </nav>

        {/* Navigation - would connect to API for real pages list */}
        <nav className="page-nav">
          <div className="nav-section-title">Workspaces</div>
          
          {window.location.pathname !== '/' && (
            <>
              <Link 
                to="/" 
                onClick={() => setSidebarOpen(true)}
                className={location.pathname === '/?view=recent' ? 'active-nav-item' : ''}
              >
                Recent
              </Link>
              
              <a href="/search" className="nav-link">
                Search...
              </a>
            </>
          )}

          {window.location.pathname !== '/' && (
            <>
              <div className="separator"></div>
              <span className="nav-spacer">Saved to</span>
              
              {/* These would be populated from API */}
              {['Favorites', 'Watched'].map(name => (
                <a key={name} href="#" className="nav-link disabled" title={`Coming soon: ${name}`}>
                  {name}
                </a>
              ))}
            </>
          )}

          {/* Collections - placeholder */}
          {!['/page/', '/search'].includes(window.location.pathname) && (
            <>
              <div className="separator"></div>
              <span className="nav-spacer">Collections</span>
              
              {['Personal', 'Work', 'Projects'].map(name => (
                <a key={name} href="#" className="nav-link disabled" title={`Coming soon: ${name}`}>
                  {name}
                </a>
              ))}
            </>
          )}

          {/* Tags - placeholder */}
          {!['/page/', '/search'].includes(window.location.pathname) && (
            <>
              <div className="separator"></div>
              <span className="nav-spacer">Tags</span>
              
              {['#urgent', '#todo', '#research'].map(tag => (
                <a key={tag} href="#" className="nav-link disabled" title={`Coming soon: ${tag}`}>
                  {tag}
                </a>
              ))}
            </>
          )}

          {/* Settings */}
          {!['/page/', '/search'].includes(window.location.pathname) && (
            <>
              <div className="separator"></div>
              <span className="nav-spacer">Settings</span>
              
              {['View settings', 'Desktop app', 'Help & Feedback', 'About Notion-like App'].map(name => (
                <a key={name} href="#" className="nav-link disabled">{name}</a>
              ))}
            </>
          )}

          {/* User profile */}
          {!['/page/', '/search'].includes(window.location.pathname) && (
            <>
              <div className="separator"></div>
              <span className="nav-spacer">User</span>
              
              {['Settings', 'My pages', 'Upgrade Pro', 'Sign out'].map(name => (
                <a key={name} href="#" className="nav-link disabled">{name}</a>
              ))}

              <div className="user-info">
                <div className="avatar-placeholder" title="Default avatar"></div>
                <span>Guest User</span>
              </div>
            </>
          )}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
