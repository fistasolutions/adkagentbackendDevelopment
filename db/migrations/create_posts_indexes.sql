-- Create indexes for the posts table to improve query performance
-- This migration adds indexes for the most frequently queried columns

-- Composite index for the main scheduled tweets query
-- This covers: status, scheduled_time (for the WHERE clause and ORDER BY)
CREATE INDEX IF NOT EXISTS idx_posts_status_scheduled_time 
ON posts(status, scheduled_time);

-- Index for user_id and account_id lookups (used in other queries)
CREATE INDEX IF NOT EXISTS idx_posts_user_account 
ON posts(user_id, account_id);

-- Index for status alone (used in various queries)
CREATE INDEX IF NOT EXISTS idx_posts_status 
ON posts(status);

-- Index for scheduled_time alone (for time-based queries)
CREATE INDEX IF NOT EXISTS idx_posts_scheduled_time 
ON posts(scheduled_time);

-- Index for created_at (used in ORDER BY clauses)
CREATE INDEX IF NOT EXISTS idx_posts_created_at 
ON posts(created_at);

-- Composite index for user_id, account_id, and status (common query pattern)
CREATE INDEX IF NOT EXISTS idx_posts_user_account_status 
ON posts(user_id, account_id, status);

-- Index for posted_time (used in some queries)
CREATE INDEX IF NOT EXISTS idx_posts_posted_time 
ON posts(posted_time);

-- Index for comments_fetched_at (used in comment-related queries)
CREATE INDEX IF NOT EXISTS idx_posts_comments_fetched_at 
ON posts(comments_fetched_at); 