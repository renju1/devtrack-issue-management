-- One-time migration for the existing DevTrack schema.
-- Assumptions: the selected database has InnoDB `issues` and `users` tables;
-- `users.user_id` is a signed INT primary key; `issues.assigned_developer`
-- is the existing text column; and the assignment ID column, index, and
-- constraint do not already exist. Run this exactly once after review.
-- It preserves issue rows and legacy assignee names and does not map names.

ALTER TABLE issues
    ADD COLUMN assigned_developer_id INT NULL AFTER assigned_developer,
    ADD INDEX idx_issues_assignee_created
        (assigned_developer_id, created_at),
    ADD CONSTRAINT fk_issues_assigned_developer
        FOREIGN KEY (assigned_developer_id) REFERENCES users (user_id)
        ON UPDATE CASCADE ON DELETE SET NULL;
