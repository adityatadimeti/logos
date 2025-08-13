import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();

  return (
    <div className="page">
      <div className="container">
        {location.pathname !== '/' && (
          <div className="nav-links">
            <Link to="/" className="nav-link">
              ← Back to Dashboard
            </Link>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
