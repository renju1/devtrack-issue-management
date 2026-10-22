
import { useEffect, useRef, useState } from 'react'
import './App.css'
import DashboardShell from './DashboardShell.jsx'

const API_URL = import.meta.env.VITE_API_URL?.replace(/\/+$/, '')

async function readApiResponse(response, fallbackMessage) {
  const contentType = response.headers.get('content-type') || ''
  let data

  if (contentType.includes('application/json')) {
    try {
      data = await response.json()
    } catch {
      throw new Error(`The API returned invalid JSON (HTTP ${response.status})`)
    }
  } else {
    const responseText = (await response.text()).trim()
    data = responseText ? { error: responseText.slice(0, 200) } : {}
  }

  if (!response.ok) {
    throw new Error(
      `${data.error || data.message || fallbackMessage} (HTTP ${response.status})`
    )
  }

  return data
}

function ProfileMenu({ user, onLogout }) {
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef(null)
  const username = user?.username || 'User'
  const role = user?.role || 'User'

  useEffect(() => {
    if (!isOpen) return undefined

    function handlePointerDown(event) {
      if (!menuRef.current?.contains(event.target)) setIsOpen(false)
    }

    function handleKeyDown(event) {
      if (event.key === 'Escape') setIsOpen(false)
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  return (
    <div className="profile-menu" ref={menuRef}>
      <button
        className="profile-trigger"
        type="button"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
      >
        <span className="profile-avatar" aria-hidden="true">
          {username.charAt(0).toUpperCase()}
        </span>
        <span className="profile-trigger-name">{username}</span>
      </button>
      {isOpen && (
        <div className="profile-dropdown" role="menu">
          <div className="profile-details">
            <strong>{username}</strong>
            <span>{role.charAt(0).toUpperCase() + role.slice(1)}</span>
          </div>
          <button
            className="profile-logout"
            type="button"
            role="menuitem"
            onClick={() => {
              setIsOpen(false)
              onLogout()
            }}
          >
            Logout
          </button>
        </div>
      )}
    </div>
  )
}

function formatIssueDate(value) {
  if (!value) return 'Unknown'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString()
}

function IssueProgress({ status }) {
  const progress = {
    Open: 20,
    'In Progress': 55,
    Resolved: 85,
    Closed: 100,
  }[status] || 0

  return (
    <div className="issue-progress" aria-label={`Progress: ${status}`}>
      <span className={`status-badge status-${status.toLowerCase().replaceAll(' ', '-')}`}>
        {status}
      </span>
      <div className="progress-track" aria-hidden="true">
        <span style={{ width: `${progress}%` }} />
      </div>
    </div>
  )
}

function ReporterIdentity({ username }) {
  const displayName = username || 'Unknown reporter'
  return (
    <div className="reporter-identity" title={displayName}>
      <span className="reporter-avatar" aria-hidden="true">
        {username ? username.charAt(0).toUpperCase() : '?'}
      </span>
      <span className="reporter-name">{displayName}</span>
    </div>
  )
}

function IssueStatusBadge({ status }) {
  return (
    <span className={`status-badge status-${status.toLowerCase().replaceAll(' ', '-')}`}>
      {status}
    </span>
  )
}

function IssueDetailsDialog({
  issue, comments, commentsLoading, commentsError, commentSuccess,
  commentText, commentSubmitting, onCommentTextChange, onSubmitComment,
  onClose,
}) {
  if (!issue) return null
  return (
    <div className="issue-details-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="issue-details-modal" role="dialog" aria-modal="true" aria-labelledby="issue-details-title">
        <div className="issue-details-heading">
          <h2 id="issue-details-title">{issue.title}</h2>
          <button className="secondary-button" onClick={onClose} aria-label="Close issue details">Close</button>
        </div>
        <div className="issue-details-scroll">
          <IssueProgress status={issue.status} />
          <p className="issue-details-description">{issue.description}</p>
          <dl className="issue-details-list">
            <div><dt>Priority</dt><dd>{issue.priority}</dd></div>
            <div><dt>Project</dt><dd>{issue.project_name || 'Unassigned'}</dd></div>
            <div><dt>Assigned developer</dt><dd>{issue.assigned_developer || 'Unassigned'}</dd></div>
            <div><dt>Created</dt><dd>{formatIssueDate(issue.created_at)}</dd></div>
          </dl>
          <section className="discussion-section" aria-labelledby="discussion-heading">
            <div className="section-heading">
              <div>
                <h3 id="discussion-heading">Discussion</h3>
                <p>Comments on this issue</p>
              </div>
            </div>
            {commentsError && <p className="error-message" role="alert">{commentsError}</p>}
            {commentSuccess && <p className="success-message" role="status">{commentSuccess}</p>}
            {commentsLoading ? <p className="empty-state">Loading comments...</p> : (
              comments.length ? (
                <ol className="comment-list">
                  {comments.map((comment) => (
                    <li className="comment-item" key={comment.comment_id}>
                      <div className="comment-meta"><strong>{comment.username}</strong><time>{formatIssueDate(comment.created_at)}</time></div>
                      <p>{comment.comment_text}</p>
                    </li>
                  ))}
                </ol>
              ) : <p className="empty-state">No comments yet. Start the discussion.</p>
            )}
            <form className="comment-form" onSubmit={onSubmitComment}>
              <label htmlFor="issue-comment-text">Add a comment</label>
              <textarea id="issue-comment-text" required maxLength={5000} rows={3} value={commentText} onChange={(event) => onCommentTextChange(event.target.value)} placeholder="Write a comment..." />
              <button className="primary-button" type="submit" disabled={commentSubmitting || !commentText.trim()}>
                {commentSubmitting ? 'Posting...' : 'Post comment'}
              </button>
            </form>
          </section>
        </div>
      </section>
    </div>
  )
}

function App() {
  const [issues, setIssues] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [showUserModal, setShowUserModal] = useState(false)
  const [page, setPage] = useState('dashboard')
  const [developers, setDevelopers] = useState([])
  const [users, setUsers] = useState([])
  const [projects, setProjects] = useState([])
  const [projectName, setProjectName] = useState('')
  const [myIssues, setMyIssues] = useState([])
  const [myIssuesLoading, setMyIssuesLoading] = useState(false)
  const [selectedIssue, setSelectedIssue] = useState(null)
  const [comments, setComments] = useState([])
  const [commentsLoading, setCommentsLoading] = useState(false)
  const [commentsError, setCommentsError] = useState('')
  const [commentSuccess, setCommentSuccess] = useState('')
  const [commentText, setCommentText] = useState('')
  const [commentSubmitting, setCommentSubmitting] = useState(false)
  const [success, setSuccess] = useState('')
  const [userForm, setUserForm] = useState({
    username: '',
    password: '',
    role: 'tester',
  })
  const [filters, setFilters] = useState({
    status: '',
    date_range: 'all',
    priority: '',
  })
  const [form, setForm] = useState({
    title: '',
    description: '',
    priority: 'Medium',
    project_id: '',
  })
  const [token, setToken] = useState(
  localStorage.getItem('access_token') || ''
  )
  const [user, setUser] = useState(() => {
  const savedUser = localStorage.getItem('user')
  return savedUser ? JSON.parse(savedUser) : null
  })
  const [loginForm, setLoginForm] = useState({
    username: '',
    password: '',
  })
  const [showLoginPassword, setShowLoginPassword] = useState(false)
  const isTester = user?.role === 'tester'
  const isDeveloper = user?.role === 'developer'
  const isAdmin = user?.role === 'admin'

  async function login(username, password) {
    try {
      setError('')

      const response = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      })

      const data = await readApiResponse(response, 'Login failed')

      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user))

      setToken(data.access_token)
      setUser(data.user)

    } catch (err) {
      setError(err.message)
    }
  }

  async function fetchIssues(activeFilters = filters) {
    try {
      setLoading(true)
      setError('')

      const query = new URLSearchParams(
        Object.fromEntries(
          Object.entries(activeFilters).filter(([, value]) => value)
        )
      ).toString()
      const response = await fetch(`${API_URL}/issues${query ? `?${query}` : ''}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await readApiResponse(response, 'Failed to load issues')
      if (!Array.isArray(data.issues)) {
        throw new Error('The API response did not contain an issue list')
      }
      setIssues(data.issues)
    } catch (err) {
      setError(err.message || 'Failed to load issues')
    } finally {
      setLoading(false)
    }
  }

  async function fetchDevelopers() {
    try {
      const response = await fetch(`${API_URL}/developers`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await readApiResponse(response, 'Failed to load developers')
      setDevelopers(data.developers || [])
    } catch (err) {
      setError(err.message)
    }
  }

  async function fetchUsers() {
    try {
      const response = await fetch(`${API_URL}/users`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await readApiResponse(response, 'Failed to load users')
      setUsers(data.users || [])
    } catch (err) {
      setError(err.message)
    }
  }

  async function fetchProjects() {
    try {
      const response = await fetch(`${API_URL}/projects`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await readApiResponse(response, 'Failed to load projects')
      setProjects(data.projects || [])
    } catch (err) {
      setError(err.message)
    }
  }

  async function fetchMyIssues() {
    setMyIssuesLoading(true)
    setError('')
    try {
      const response = await fetch(`${API_URL}/my/issues`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await readApiResponse(response, 'Failed to load your issues')
      setMyIssues(data.issues || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setMyIssuesLoading(false)
    }
  }

  async function openIssueDetails(issueId) {
    setError('')
    setComments([])
    setCommentsError('')
    setCommentSuccess('')
    setCommentText('')
    try {
      const response = await fetch(`${API_URL}/issues/${issueId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await readApiResponse(response, 'Failed to load issue details')
      setSelectedIssue(data.issue)
      await fetchIssueComments(issueId)
    } catch (err) {
      setError(err.message)
    }
  }

  async function fetchIssueComments(issueId) {
    setCommentsLoading(true)
    setCommentsError('')
    try {
      const response = await fetch(`${API_URL}/issues/${issueId}/comments`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await readApiResponse(response, 'Failed to load comments')
      setComments(data.comments || [])
    } catch (err) {
      setCommentsError(err.message || 'Failed to load comments')
    } finally {
      setCommentsLoading(false)
    }
  }

  async function submitIssueComment(event) {
    event.preventDefault()
    if (!selectedIssue || !commentText.trim()) return
    setCommentSubmitting(true)
    setCommentsError('')
    setCommentSuccess('')
    try {
      const response = await fetch(`${API_URL}/issues/${selectedIssue.issue_id}/comments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ comment_text: commentText }),
      })
      await readApiResponse(response, 'Failed to post comment')
      setCommentText('')
      setCommentSuccess('Comment added.')
      await fetchIssueComments(selectedIssue.issue_id)
    } catch (err) {
      setCommentsError(err.message || 'Failed to post comment')
    } finally {
      setCommentSubmitting(false)
    }
  }

  function closeIssueDetails() {
    setSelectedIssue(null)
    setComments([])
    setCommentsError('')
    setCommentSuccess('')
    setCommentText('')
  }

  useEffect(() => {
    if (token && user) {
      fetchIssues()
      fetchProjects()
      if (user.role === 'admin') {
        fetchDevelopers()
        fetchUsers()
      }
    } else {
      setLoading(false)
    }
  }, [token, user])
  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')

    setToken('')
    setUser(null)
    setIssues([])
    setUsers([])
    setError('')
    setSuccess('')
    setPage('dashboard')
  }
  async function createIssue(event) {
    event.preventDefault()

    try {
      const response = await fetch(`${API_URL}/issues`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(form),
      })

      await readApiResponse(response, 'Failed to create issue')

      setForm({
        title: '',
        description: '',
        priority: 'Medium',
        project_id: '',
      })
      setShowForm(false)
      await fetchIssues()
    } catch (err) {
      setError(err.message)
    }
  }

  async function createUser(event) {
    event.preventDefault()
    setError('')
    setSuccess('')

    try {
      const response = await fetch(`${API_URL}/users`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(userForm),
      })
      const data = await readApiResponse(response, 'Failed to create user')
      setShowUserModal(false)
      setUserForm({ username: '', password: '', role: 'tester' })
      setSuccess(data.message || 'User created successfully')
      await fetchUsers()
    } catch (err) {
      setError(err.message)
    }
  }

  async function createProject(event) {
    event.preventDefault()
    setError('')
    setSuccess('')
    try {
      const response = await fetch(`${API_URL}/projects`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ name: projectName }),
      })
      const data = await readApiResponse(response, 'Failed to create project')
      setProjectName('')
      setSuccess(data.message || 'Project created successfully')
      await fetchProjects()
    } catch (err) {
      setError(err.message)
    }
  }

  async function deleteUser(managedUser) {
    if (!window.confirm(`Delete account "${managedUser.username}"?`)) return

    setError('')
    setSuccess('')
    try {
      const response = await fetch(`${API_URL}/users/${managedUser.user_id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await readApiResponse(response, 'Failed to delete user')
      setSuccess(data.message || 'User deleted successfully')
      await fetchUsers()
    } catch (err) {
      setError(err.message)
    }
  }

  async function assignIssue(issue, developerId) {
    try {
      const response = await fetch(
        `${API_URL}/issues/${issue.issue_id}/assignee`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            assignee_user_id: developerId ? Number(developerId) : null,
          }),
        }
      )
      await readApiResponse(response, 'Failed to assign issue')
      await fetchIssues()
    } catch (err) {
      setError(err.message)
    }
  }

  async function updateStatus(issue, status) {
    try {
      const response = await fetch(
        `${API_URL}/issues/${issue.issue_id}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ status }),
        }
      )

      await readApiResponse(response, 'Failed to update issue')

      await fetchIssues()
    } catch (err) {
      setError(err.message)
    }
  }

  async function deleteIssue(issueId) {
    if (!window.confirm('Are you sure you want to delete this issue?')) {
      return
    }

    try {
      const response = await fetch(
        `${API_URL}/issues/${issueId}`,
        {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      await readApiResponse(response, 'Failed to delete issue')

      await fetchIssues()
    } catch (err) {
      setError(err.message)
    }
  }

  const openCount = issues.filter(
    (issue) => issue.status === 'Open'
  ).length

  const progressCount = issues.filter(
    (issue) => issue.status === 'In Progress'
  ).length

  const resolvedCount = issues.filter(
    (issue) => issue.status === 'Resolved' || issue.status === 'Closed'
  ).length
  const hasActiveFilters = filters.status !== ''
    || filters.date_range !== 'all'
    || filters.priority !== ''
  
  if (!token || !user) {
    return (
      <main className="dashboard login-page">
        <form
          className="issue-form"
          onSubmit={(event) => {
            event.preventDefault()
            login(loginForm.username, loginForm.password)
          }}
        >
          <h1>DevTrack Login</h1>
          <p>Sign in to manage your issues.</p>

          <label>
            Username
            <input
              type="text"
              required
              value={loginForm.username}
              onChange={(event) =>
                setLoginForm({
                  ...loginForm,
                  username: event.target.value,
                })
              }
              placeholder="Enter username"
            />
          </label>

          <label>
            Password
            <div className="password-input-wrap">
              <input
                type={showLoginPassword ? 'text' : 'password'}
                required
                autoComplete="current-password"
                value={loginForm.password}
                onChange={(event) =>
                  setLoginForm({
                    ...loginForm,
                    password: event.target.value,
                  })
                }
                placeholder="Enter password"
              />
              <button
                className="password-visibility-toggle"
                type="button"
                aria-label={showLoginPassword ? 'Hide password' : 'Show password'}
                aria-pressed={showLoginPassword}
                onClick={() => setShowLoginPassword((visible) => !visible)}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  {showLoginPassword ? (
                    <>
                      <path d="M3 3l18 18" />
                      <path d="M10.6 10.6a2 2 0 002.8 2.8" />
                      <path d="M9.9 5.2A10.8 10.8 0 0112 5c5.2 0 8.8 4.4 9.7 6-.4.7-1.3 1.8-2.5 2.8M6.2 6.2C3.9 7.6 2.6 9.7 2.3 11c.9 1.6 4.5 6 9.7 6 1.1 0 2.1-.2 3-.5" />
                    </>
                  ) : (
                    <>
                      <path d="M2.3 12s3.5-7 9.7-7 9.7 7 9.7 7-3.5 7-9.7 7-9.7-7-9.7-7z" />
                      <circle cx="12" cy="12" r="3" />
                    </>
                  )}
                </svg>
              </button>
            </div>
          </label>

          {error && <p className="error-message">{error}</p>}

          <button className="primary-button" type="submit">
            Login
          </button>
        </form>
      </main>
    )
  }

  if (isTester && page === 'my-issues') {
    return (
      <DashboardShell
        user={user}
        profileMenu={<ProfileMenu user={user} onLogout={logout} />}
        title="My Issues"
        subtitle="Issues created by your account."
        activePage="my-issues"
        navItems={[
          { id: 'dashboard', label: 'Issues', icon: 'issues', onClick: () => setPage('dashboard') },
          { id: 'my-issues', label: 'My Issues', icon: 'inbox', onClick: () => fetchMyIssues() },
        ]}
        actions={(
          <button className="secondary-button" onClick={() => setPage('dashboard')}>
            Back to Dashboard
          </button>
        )}
      >

        {error && <p className="error-message" role="alert">{error}</p>}
        {myIssuesLoading ? (
          <p className="empty-state">Loading your issues...</p>
        ) : myIssues.length === 0 ? (
          <p className="empty-state">You have not reported any issues yet.</p>
        ) : (
          <div className="issue-list my-issue-list">
            {myIssues.map((issue) => (
              <article className="issue-card issue-board-row my-issue-board-row" key={issue.issue_id}>
                <div className="issue-board-summary">
                  <h3>{issue.title}</h3>
                  <div className="issue-board-subline">
                    <span>#{issue.issue_id}</span>
                    <span>Created {formatIssueDate(issue.created_at)}</span>
                  </div>
                  <p className="issue-description">{issue.description}</p>
                </div>
                <div className="issue-board-cell">
                  <span className="issue-board-label">Reporter</span>
                  <ReporterIdentity username={issue.reporter_username} />
                </div>
                <div className="issue-board-cell">
                  <span className="issue-board-label">Priority</span>
                  <span className={`priority priority-${issue.priority.toLowerCase()}`}>{issue.priority}</span>
                </div>
                <div className="issue-board-cell">
                  <span className="issue-board-label">Status</span>
                  <IssueStatusBadge status={issue.status} />
                </div>
                <div className="issue-board-cell">
                  <span className="issue-board-label">Project</span>
                  <span className="issue-board-value">{issue.project_name || 'Unassigned'}</span>
                </div>
                <div className="issue-board-cell">
                  <span className="issue-board-label">Assigned developer</span>
                  <span className="issue-board-value">{issue.assigned_developer || 'Unassigned'}</span>
                </div>
                <button
                  className="secondary-button issue-details-button"
                  aria-label={`View details and discussion for issue ${issue.issue_id}`}
                  onClick={() => openIssueDetails(issue.issue_id)}
                >View details</button>
              </article>
            ))}
          </div>
        )}

        <IssueDetailsDialog
          issue={selectedIssue} comments={comments} commentsLoading={commentsLoading}
          commentsError={commentsError} commentSuccess={commentSuccess}
          commentText={commentText} commentSubmitting={commentSubmitting}
          onCommentTextChange={setCommentText} onSubmitComment={submitIssueComment}
          onClose={closeIssueDetails}
        />
      </DashboardShell>
    )
  }

  if (isAdmin && page === 'accounts') {
    return (
      <DashboardShell
        user={user}
        profileMenu={<ProfileMenu user={user} onLogout={logout} />}
        title="Manage Accounts"
        subtitle="Create and manage DevTrack users."
        activePage="accounts"
        navItems={[
          { id: 'dashboard', label: 'Issues', icon: 'issues', onClick: () => setPage('dashboard') },
          { id: 'accounts', label: 'Manage Accounts', icon: 'users', onClick: () => setPage('accounts') },
          { id: 'projects', label: 'Manage Projects', icon: 'projects', onClick: () => setPage('projects') },
        ]}
        actions={(
          <button className="secondary-button" onClick={() => setPage('dashboard')}>
            Back to Dashboard
          </button>
        )}
      >

        {error && <p className="error-message" role="alert">{error}</p>}
        {success && <p className="success-message" role="status">{success}</p>}

        <section className="users-section">
          <div className="section-heading">
            <div>
              <h2>Users</h2>
              <p>Username and role</p>
            </div>
            <button
              className="primary-button"
              onClick={() => {
                setError('')
                setSuccess('')
                setShowUserModal(true)
              }}
            >
              + Add User
            </button>
          </div>
          <div className="user-list" aria-live="polite">
            {users.map((managedUser) => (
              <article className="user-row" key={managedUser.user_id}>
                <strong>{managedUser.username}</strong>
                <span className="user-role">{managedUser.role}</span>
                <button
                  className="delete-button"
                  onClick={() => deleteUser(managedUser)}
                >
                  Delete
                </button>
              </article>
            ))}
          </div>
        </section>

        {showUserModal && (
          <div
            className="modal-backdrop"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                setShowUserModal(false)
                setUserForm({ username: '', password: '', role: 'tester' })
              }
            }}
          >
            <form
              className="user-modal"
              onSubmit={createUser}
              role="dialog"
              aria-modal="true"
              aria-labelledby="add-user-title"
            >
              <h2 id="add-user-title">Add User</h2>
              {error && <p className="error-message" role="alert">{error}</p>}
              <label>
                Username
                <input
                  required
                  autoComplete="off"
                  value={userForm.username}
                  onChange={(event) =>
                    setUserForm({ ...userForm, username: event.target.value })
                  }
                />
              </label>
              <label>
                Password
                <input
                  required
                  type="password"
                  autoComplete="new-password"
                  value={userForm.password}
                  onChange={(event) =>
                    setUserForm({ ...userForm, password: event.target.value })
                  }
                />
              </label>
              <label>
                Role
                <select
                  value={userForm.role}
                  onChange={(event) =>
                    setUserForm({ ...userForm, role: event.target.value })
                  }
                >
                  <option value="tester">Tester</option>
                  <option value="developer">Developer</option>
                  <option value="admin">Admin</option>
                </select>
              </label>
              <div className="modal-actions">
                <button className="primary-button" type="submit">Create User</button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => {
                    setShowUserModal(false)
                    setUserForm({ username: '', password: '', role: 'tester' })
                    setError('')
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}
      </DashboardShell>
    )
  }

  if (isAdmin && page === 'projects') {
    return (
      <DashboardShell
        user={user}
        profileMenu={<ProfileMenu user={user} onLogout={logout} />}
        title="Manage Projects"
        subtitle="Create and manage projects available for issue reporting."
        activePage="projects"
        navItems={[
          { id: 'dashboard', label: 'Issues', icon: 'issues', onClick: () => setPage('dashboard') },
          { id: 'accounts', label: 'Manage Accounts', icon: 'users', onClick: () => setPage('accounts') },
          { id: 'projects', label: 'Manage Projects', icon: 'projects', onClick: () => setPage('projects') },
        ]}
        actions={(
          <button className="secondary-button" onClick={() => setPage('dashboard')}>
            Back to Dashboard
          </button>
        )}
      >
        {error && <p className="error-message" role="alert">{error}</p>}
        {success && <p className="success-message" role="status">{success}</p>}
        <section className="projects-admin-section">
          <div className="section-heading">
            <div>
              <h2>Projects</h2>
              <p>Projects available when testers report issues.</p>
            </div>
          </div>
          <form className="project-create-form" onSubmit={createProject}>
            <label>
              Project name
              <input
                required
                maxLength={100}
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                placeholder="Enter a project name"
              />
            </label>
            <button className="primary-button" type="submit">Create Project</button>
          </form>
          {projects.length === 0 ? (
            <p className="empty-state">Create the first project to enable issue reporting.</p>
          ) : (
            <ul className="project-list">
              {projects.map((project) => (
                <li key={project.project_id}>{project.name}</li>
              ))}
            </ul>
          )}
        </section>
      </DashboardShell>
    )
  }
  
  return (
    <DashboardShell
      user={user}
      profileMenu={<ProfileMenu user={user} onLogout={logout} />}
      title={isDeveloper ? 'Assigned Issues' : 'Issues'}
      subtitle={isDeveloper ? 'Issues assigned to your account.' : 'Track issues, priorities, and project progress.'}
      activePage="dashboard"
      navItems={[
        {
          id: 'dashboard',
          label: isDeveloper ? 'Assigned Issues' : 'Issues',
          icon: 'issues',
          onClick: () => setPage('dashboard'),
        },
        ...(isTester ? [{
          id: 'my-issues',
          label: 'My Issues',
          icon: 'inbox',
          onClick: () => {
            setPage('my-issues')
            fetchMyIssues()
          },
        }] : []),
        ...(isAdmin ? [{
          id: 'projects',
          label: 'Manage Projects',
          icon: 'projects',
          onClick: () => {
            setError('')
            setSuccess('')
            setPage('projects')
          },
        }] : []),
        ...(isAdmin ? [{
          id: 'accounts',
          label: 'Manage Accounts',
          icon: 'users',
          onClick: () => {
            setError('')
            setSuccess('')
            setPage('accounts')
          },
        }] : []),
      ]}
      actions={isTester && (
        <button
          className="primary-button"
          type="button"
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? 'Cancel' : '+ New Issue'}
        </button>
      )}
    >

      <section className="stats">
        <article className="stat-card">
          <span>Total Issues</span>
          <strong>{issues.length}</strong>
        </article>
        <article className="stat-card">
          <span>Open</span>
          <strong>{openCount}</strong>
        </article>
        <article className="stat-card">
          <span>In Progress</span>
          <strong>{progressCount}</strong>
        </article>
        <article className="stat-card">
          <span>Resolved / Closed</span>
          <strong>{resolvedCount}</strong>
        </article>
      </section>

      {isTester && showForm && (
        <form className="issue-form" onSubmit={createIssue}>
          <h2>Create an issue</h2>

          <label>
            Title
            <input
              required
              maxLength={150}
              value={form.title}
              onChange={(event) =>
                setForm({ ...form, title: event.target.value })
              }
              placeholder="e.g. Login button not working"
            />
          </label>

          <label>
            Description
            <textarea
              required
              value={form.description}
              onChange={(event) =>
                setForm({ ...form, description: event.target.value })
              }
              placeholder="Describe the issue"
              rows={3}
            />
          </label>

          <div className="form-row">
            <label>
              Project
              <select
                required
                value={form.project_id}
                onChange={(event) =>
                  setForm({ ...form, project_id: event.target.value })
                }
              >
                <option value="">Select a project</option>
                {projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Priority
              <select
                value={form.priority}
                onChange={(event) =>
                  setForm({ ...form, priority: event.target.value })
                }
              >
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
                <option>Critical</option>
              </select>
            </label>

          </div>

          <button className="primary-button" type="submit">
            Create Issue
          </button>
        </form>
      )}

      {error && (
        <div className="error-message">
          {error}
          <button onClick={fetchIssues}>Retry</button>
        </div>
      )}

      {success && <p className="success-message" role="status">{success}</p>}

      <section className="issues-section">
        <form
          className="issue-filters"
          onSubmit={(event) => {
            event.preventDefault()
            fetchIssues()
          }}
        >
          <label>
            Status
            <select
              value={filters.status}
              onChange={(event) =>
                setFilters({ ...filters, status: event.target.value })
              }
            >
              <option value="">All statuses</option>
              <option>Open</option>
              <option>In Progress</option>
              <option>Resolved</option>
              <option>Closed</option>
            </select>
          </label>
          <label>
            Date range
            <select
              value={filters.date_range}
              onChange={(event) =>
                setFilters({ ...filters, date_range: event.target.value })
              }
            >
              <option value="10">Last 10 days</option>
              <option value="30">Last 30 days</option>
              <option value="all">All time</option>
            </select>
          </label>
          <label>
            Priority
            <select
              value={filters.priority}
              onChange={(event) =>
                setFilters({ ...filters, priority: event.target.value })
              }
            >
              <option value="">All priorities</option>
              <option>Low</option>
              <option>Medium</option>
              <option>High</option>
              <option>Critical</option>
            </select>
          </label>
          <div className="filter-actions">
            <button className="primary-button" type="submit">Apply filters</button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => {
                const emptyFilters = {
                  status: '',
                  date_range: 'all',
                  priority: '',
                }
                setFilters(emptyFilters)
                fetchIssues(emptyFilters)
              }}
            >
              Clear
            </button>
          </div>
        </form>

        <div className="section-heading">
          <div>
            <h2>Issues</h2>
            <p>
              {isDeveloper
                ? 'Issues assigned to you'
                : 'All issues stored in your DevTrack database'}
            </p>
          </div>
          <button className="secondary-button" onClick={fetchIssues}>
            Refresh
          </button>
        </div>

        {loading ? (
          <p className="empty-state">Loading issues...</p>
        ) : issues.length === 0 ? (
          <p className="empty-state">
            {hasActiveFilters
              ? 'No issues match these filters.'
              : isDeveloper
                ? 'No issues are assigned to you yet.'
                : 'No issues yet. Create your first issue to get started.'}
          </p>
        ) : (
          <div className="issue-list">
            {issues.map((issue) => (
              <article className="issue-card issue-board-row" key={issue.issue_id}>
                <div className="issue-board-summary">
                  <h3>{issue.title}</h3>
                  <div className="issue-board-subline"><span>#{issue.issue_id}</span></div>
                  <p className="issue-description">{issue.description}</p>
                </div>
                <div className="issue-board-cell">
                  <span className="issue-board-label">Reporter</span>
                  <ReporterIdentity username={issue.reporter_username} />
                </div>
                <div className="issue-board-cell">
                  <span className="issue-board-label">Priority</span>
                  <span className={`priority priority-${issue.priority.toLowerCase()}`}>{issue.priority}</span>
                </div>
                <div className="issue-board-cell">
                  <span className="issue-board-label">Status</span>
                  {isDeveloper ? (
                    <select
                      className="issue-board-status-select"
                      aria-label={`Status for issue ${issue.issue_id}`}
                      value={issue.status}
                      onChange={(event) => updateStatus(issue, event.target.value)}
                    >
                      <option>Open</option>
                      <option>In Progress</option>
                      <option>Resolved</option>
                      <option>Closed</option>
                    </select>
                  ) : <IssueStatusBadge status={issue.status} />}
                </div>
                <div className="issue-board-cell">
                  <span className="issue-board-label">Project</span>
                  <span className="issue-board-value">{issue.project_name || 'Unassigned'}</span>
                </div>
                <div className="issue-board-cell">
                  <span className="issue-board-label">Assigned developer</span>
                  <span className="issue-board-value">{issue.assigned_developer || 'Unassigned'}</span>
                </div>
                <button className="secondary-button issue-details-button" aria-label={`View details and discussion for issue ${issue.issue_id}`} onClick={() => openIssueDetails(issue.issue_id)}>
                  View details
                </button>

                {isAdmin && (
                  <div className="issue-board-controls">
                    <label>
                      <span>Assigned developer</span>
                      <select
                        value={issue.assigned_developer_id || ''}
                        onChange={(event) => assignIssue(issue, event.target.value)}
                      >
                        <option value="">Unassigned</option>
                        {developers.map((developer) => (
                          <option key={developer.user_id} value={developer.user_id}>
                            {developer.username}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button className="delete-button" onClick={() => deleteIssue(issue.issue_id)}>
                      Delete
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
      <IssueDetailsDialog
        issue={selectedIssue} comments={comments} commentsLoading={commentsLoading}
        commentsError={commentsError} commentSuccess={commentSuccess}
        commentText={commentText} commentSubmitting={commentSubmitting}
        onCommentTextChange={setCommentText} onSubmitComment={submitIssueComment}
        onClose={closeIssueDetails}
      />
    </DashboardShell>
  )
}

export default App
