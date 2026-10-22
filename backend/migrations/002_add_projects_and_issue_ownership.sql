-- Adds project links and tester ownership without assigning existing issues.
-- Live schema review (2026-10-22): issues and users are InnoDB; both user_id
-- and issue_id are signed INT primary keys. There are 3 existing issues and
-- no projects table, project_id, or created_by_user_id column.
-- Existing issue rows retain NULL project and creator links until a safe,
-- evidence-based backfill is approved and performed separately.

CREATE TABLE projects (
    project_id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id),
    UNIQUE KEY uq_projects_name (name)
) ENGINE=InnoDB;

ALTER TABLE issues
    ADD COLUMN project_id INT NULL AFTER issue_id,
    ADD COLUMN created_by_user_id INT NULL AFTER project_id,
    ADD INDEX idx_issues_project_created_at (project_id, created_at),
    ADD INDEX idx_issues_creator_created_at (created_by_user_id, created_at),
    ADD CONSTRAINT fk_issues_project
        FOREIGN KEY (project_id) REFERENCES projects (project_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    ADD CONSTRAINT fk_issues_created_by_user
        FOREIGN KEY (created_by_user_id) REFERENCES users (user_id)
        ON UPDATE CASCADE ON DELETE RESTRICT;
