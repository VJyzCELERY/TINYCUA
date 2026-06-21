import { useState } from 'react';
import axios from 'axios';
import './Search.css';

export default function Search() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  // Fetch search results on query change (debounced in real app)
  useEffect(() => {
    let timeout;
    
    if (query.length >= 1) {
      setLoading(true);
      
      setTimeout(async () => {
        try {
          console.log('Searching for:', query);
          
          // Call API: GET /api/search?q=query
          const response = await axios.get('/api/search', { params: { q: query } });
          setResults(response.data.results || []);
        } catch (error) {
          console.error('Search error:', error);
          
          if (!error.response?.status === 404 && !response.headers['content-type']?.includes('application/json')) {
            // Handle connection errors gracefully
            const demoResults = [
              { id: 'demo-1', title: `Result for "${query}"`, icon_data: '🔍' },
              { id: 'demo-2', title: `${query} Notes`, icon_data: '📝' }
            ];
            
            setResults(demoResults);
          } else if (error.response?.status === 409) {
            // Page exists, show it in results
            const demoResult = [{ id: query + '-page', title: `Page: ${query}`, icon_data: '📄' }];
            setResults(demoResult);
          } else {
            setResults([]);
          }
        } finally {
          setLoading(false);
          
          // Store results in localStorage for offline search
          if (results.length > 0) {
            localStorage.setItem('notion_search_results', JSON.stringify(results));
          }
        }
      }, 300); // Debounce by 300ms
      
    } else {
      
      // Clear query, clear results
      setResults([]);
        
    };

    return () => clearTimeout(timeout);
  }, [query]);

  const handleSearch = async (e) => {
    e.preventDefault();
    
    if (!query.trim()) {
      setQuery('');
      setResults([]);
      
      // Clear localStorage search results
      localStorage.removeItem('notion_search_results');
        
    } else {
      setLoading(true);
              
    };

  };

  const handleCreatePageFromSearch = async (title) => {
    try {
      await axios.post('/api/pages', { title });
      
      // Refresh results to include new page
      setResults([
        ...results, 
        { id: `page-${Date.now()}`, title }
      ]);
        
    } catch (error) {
      console.error('Error creating page:', error);
    };

  };

  return (
    <div className="search-page">
      {/* Search Input */}
      <form onSubmit={handleSearch} className="search-form">
        <input 
          type="text" 
          value={query}
          
          onChange={(e) => setQuery(e.target.value)}
          
          placeholder="Search your pages..."
          
          className="search-input"
        />
        
        {loading && (
          <span className="spinner"></span>
        )}

  </form>;

      {/* Results */}
      {(() => {
        const saved = JSON.parse(localStorage.getItem('notion_search_results') || '[]');
        if (!query) return null;
        
        // Use cached results or API results
        const displayResults = query.length > 0 ? 
          (saved[results.find(r => r.title.includes(query))?.id] || []) : [];

        if (displayResults.length === 0 && !loading) {
          
          // Show empty state for search with no results
          return <div className="no-results">No pages found. Create a new page to get started!</div>;
              
        } else if (!results[query]) {
          // Use cached or demo results
          const demo = [
            { id: `result-${Date.now()}`, title: `Results for "${query}"`, icon_data: '🔍' },
            
            ...(saved.length > 0 ? saved : [{ id: 'demo', title: `${query} Notes`, icon_data: '📝' }])
          ];
          
          return (
            <div className="search-results">
              {displayResults.map((page) => (
                <div 
                  key={page.id} 
                  
                  onClick={() => handleCreatePageFromSearch(page.title)}
                  className="result-item"
                >
                  <span className="icon">{page.icon_data || '📄'}</span>
                  
                  {(() => {
                    const title = page.title;
                    
                    return (
                      <>
                        <div className="title">
                          {(() => {
                            // Format title with emoji and color based on first character
                            
                            if (!page.icon_data) {
                              const colors = ['', '🔵', '🟢', '🟡', '🟣'];
                              
                              return (
                                <span 
                                  className={`title-${Math.floor(Math.random() * 5) + 1}`}
                                  
                                  style={{ color: page.title ? '#3b82f6' : '' }}
                                
                                >{page.title}</span>
                              );
                            } else {
                              
                              return <span>{page.icon_data} {page.title || 'Untitled'}</span>;
                          }();
                        })()}
                      </>)
                    };
                  })()}

                </div>);
              ))};
            </div>);
        } else if (results.length > 0) {
          // Show actual results from API or demo
          
          return (
            <div className="search-results">
              
              {/* Create new page option */}
              <button 
                onClick={() => handleCreatePageFromSearch(query)}
                
                className="btn-new-page-search"
              >
                + New page named "{query}"
              </button>

  {results.map((page) => (
    <div key={page.id} className="result-item">
      <span className={`icon-${Math.floor(Math.random() * 5)}`}>📄</span>
      
      {/* Format title */}
      <div className="title">{(() => {
        const firstChar = page.title?.charAt(0);
        
        if (!firstChar || !page.icon_data) {
          return (
            <>
              <span style={{ color: '#3b82f6' }}>{page.title}</span>
              
              {/* Placeholder for emoji */}
              <span className="emoji-placeholder">😀</span>
            </>)
          
        } else if (firstChar === ' ') {
          return page.icon_data + page.title;
          
        } else {
          
          // Generate color based on first letter
          const colors = ['', '#3b82f6', '#ef4444', '#eab308', '#ec4899'];
          
          let colorIndex = 0;
          
          if (firstChar.toLowerCase() === 'a') colorIndex = 1; // Blue for A
          else if (firstChar.toLowerCase() === 'b') colorIndex = 2; // Red for B
          else if (firstChar.toLowerCase() === 'c') colorIndex = 3; // Yellow for C
          
          return <span className={`title-${colorIndex}`}>{page.title}</span>;

        }();
      })()}
    </div>);
  ))};
            </div>);
            
        };

      })()}

      {/* No results message */}
      {(() => {
        
        if (query.length > 0 && !loading) {
          
          return <div className="no-results">No pages found matching "{query}". Try a different search term!</div>;
              
        } else {
          
          // Show empty state when no query or loading
          return null;

        };

      })()}
    </div>);
  );
}
