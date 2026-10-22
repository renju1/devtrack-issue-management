-- Apply after reviewing the DevTrack schema. This migration only creates
-- comments; it does not change existing issues or user records.
-- issue_id and user_id are signed INT, matching the existing primary keys.

CREATE TABLE issue_comments (
    comment_id INT NOT NULL AUTO_INCREMENT,
    issue_id INT NOT NULL,
    user_id INT NOT NULL,
    comment_text TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (comment_id),
    CONSTRAINT chk_issue_comments_nonempty
        CHECK (CHAR_LENGTH(TRIM(comment_text)) > 0),
    KEY idx_issue_comments_issue_created (issue_id, created_at, comment_id),
    KEY idx_issue_comments_user_created (user_id, created_at),
    CONSTRAINT fk_issue_comments_issue
        FOREIGN KEY (issue_id) REFERENCES issues (issue_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_issue_comments_user
        FOREIGN KEY (user_id) REFERENCES users (user_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
