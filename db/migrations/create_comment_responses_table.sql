CREATE TABLE IF NOT EXISTS comment_responses (
    id SERIAL PRIMARY KEY,
    comment_id VARCHAR(255) NOT NULL,
    post_id VARCHAR(255) NOT NULL,
    response_text TEXT NOT NULL,
    scheduled_time TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'scheduled',
    user_id VARCHAR(255) NOT NULL,
    account_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id, account_id) REFERENCES personas(user_id, account_id)
);

CREATE INDEX IF NOT EXISTS idx_comment_responses_scheduled_time 
ON comment_responses(scheduled_time);

CREATE INDEX IF NOT EXISTS idx_comment_responses_status 
ON comment_responses(status);

CREATE INDEX IF NOT EXISTS idx_comment_responses_user_account 
ON comment_responses(user_id, account_id);

-- Add columns to post_reply table if they do not exist
ALTER TABLE IF EXISTS post_reply ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY;
ALTER TABLE IF EXISTS post_reply ADD COLUMN IF NOT EXISTS post_id VARCHAR(255);
ALTER TABLE IF EXISTS post_reply ADD COLUMN IF NOT EXISTS original_post_url TEXT;
ALTER TABLE IF EXISTS post_reply ADD COLUMN IF NOT EXISTS user_id BIGINT;
ALTER TABLE IF EXISTS post_reply ADD COLUMN IF NOT EXISTS account_id BIGINT;
ALTER TABLE IF EXISTS post_reply ADD COLUMN IF NOT EXISTS competitor_username VARCHAR(255);
ALTER TABLE IF EXISTS post_reply ADD COLUMN IF NOT EXISTS generated_comment TEXT;
ALTER TABLE IF EXISTS post_reply ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE IF EXISTS post_reply ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(); 