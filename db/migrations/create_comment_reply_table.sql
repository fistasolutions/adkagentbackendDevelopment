CREATE TABLE IF NOT EXISTS comment_reply (
    id SERIAL PRIMARY KEY,
    comment_id VARCHAR(255) NOT NULL,
    post_id VARCHAR(255) NOT NULL,
    tweet_id VARCHAR(255) NOT NULL,
    tweet_url VARCHAR(255) NOT NULL,
    original_comment TEXT NOT NULL,
    reply_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    risk_score INTEGER NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    account_id VARCHAR(255) NOT NULL,
    FOREIGN KEY (user_id, account_id) REFERENCES personas(user_id, account_id)
);

CREATE INDEX IF NOT EXISTS idx_comment_reply_comment_id 
ON comment_reply(comment_id);

CREATE INDEX IF NOT EXISTS idx_comment_reply_user_account 
ON comment_reply(user_id, account_id);

CREATE INDEX IF NOT EXISTS idx_comment_reply_tweet_id
ON comment_reply(tweet_id); 