CREATE TABLE IF NOT EXISTS post_reply (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(255) NOT NULL,
    original_post_url TEXT,
    user_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    competitor_username VARCHAR(255) NOT NULL,
    generated_comment TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_post_reply_post_id ON post_reply(post_id);
CREATE INDEX IF NOT EXISTS idx_post_reply_user_account ON post_reply(user_id, account_id);
CREATE INDEX IF NOT EXISTS idx_post_reply_competitor ON post_reply(competitor_username);
CREATE INDEX IF NOT EXISTS idx_post_reply_created_at ON post_reply(created_at); 