import { useState } from 'react'
import './DashboardShell.css'

function SidebarIcon({ name }) {
  const common = {
    viewBox: '0 0 24 24',
    'aria-hidden': true,
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
  }

  if (name === 'users') {
    return <svg {...common}><circle cx="9" cy="8" r="3" /><path d="M3.5 19v-1.5A4.5 4.5 0 018 13h2a4.5 4.5 0 014.5 4.5V19zM16 5.5a3 3 0 010 5.8M17 13h.5a4 4 0 014 4v2h-4" /></svg>
  }

  if (name === 'inbox') {
    return <svg {...common}><path d="M4 4h16l1 11v5H3v-5L4 4z" /><path d="M3 14h5l2 3h4l2-3h5" /></svg>
  }

  return <svg {...common}><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h5" /></svg>
}

export default function DashboardShell({
  user,
  profileMenu,
  title,
  subtitle,
  activePage,
  navItems,
  actions,
  children,
}) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  function navigate(item) {
    setIsSidebarOpen(false)
    item.onClick()
  }

  return (
    <div className="dashboard-layout">
      {isSidebarOpen && (
        <button
          className="dashboard-sidebar-backdrop"
          type="button"
          aria-label="Close navigation menu"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}
      <aside
        className={`dashboard-sidebar${isSidebarOpen ? ' is-open' : ''}`}
        id="devtrack-sidebar"
        aria-label="Main navigation"
      >
        <div className="dashboard-brand-row">
          <a className="dashboard-brand" href="#dashboard" onClick={(event) => {
            event.preventDefault()
            const dashboardItem = navItems.find((item) => item.id === 'dashboard')
            if (dashboardItem) navigate(dashboardItem)
          }}>
            <span className="dashboard-brand-mark" aria-hidden="true">D</span>
            <span>DevTrack<small>ISSUE MANAGEMENT</small></span>
          </a>
          <button
            className="dashboard-sidebar-close"
            type="button"
            aria-label="Close navigation menu"
            onClick={() => setIsSidebarOpen(false)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>
        <div className="dashboard-sidebar-section">WORKSPACE</div>
        <nav className="dashboard-navigation">
          {navItems.map((item) => (
            <button
              className={`dashboard-nav-item${activePage === item.id ? ' is-active' : ''}`}
              key={item.id}
              type="button"
              aria-current={activePage === item.id ? 'page' : undefined}
              onClick={() => navigate(item)}
            >
              <SidebarIcon name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="dashboard-sidebar-footer">
          <span className="dashboard-sidebar-avatar" aria-hidden="true">
            {(user?.username || 'U').charAt(0).toUpperCase()}
          </span>
          <span className="dashboard-sidebar-user">
            <strong>{user?.username || 'User'}</strong>
            <small>{user?.role || 'User'}</small>
          </span>
        </div>
      </aside>

      <div className="dashboard-main">
        <header className="dashboard-topbar">
          <div className="dashboard-topbar-heading">
            <button
              className="dashboard-menu-toggle"
              type="button"
              aria-label={isSidebarOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-controls="devtrack-sidebar"
              aria-expanded={isSidebarOpen}
              onClick={() => setIsSidebarOpen((open) => !open)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
            </button>
            <div className="dashboard-page-heading">
              <h1>{title}</h1>
              {subtitle && <p>{subtitle}</p>}
            </div>
          </div>
          <div className="dashboard-topbar-actions">
            {actions}
            {profileMenu}
          </div>
        </header>
        <main className="dashboard-content">{children}</main>
      </div>
    </div>
  )
}
