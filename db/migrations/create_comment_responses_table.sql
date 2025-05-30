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