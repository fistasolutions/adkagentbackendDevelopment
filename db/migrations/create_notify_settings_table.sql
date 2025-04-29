CREATE TABLE IF NOT EXISTS notify_settings (
    notify_id SERIAL PRIMARY KEY,
    posting_day VARCHAR(255) NOT NULL,
    posting_time VARCHAR(255) NOT NULL,
    sentence_length INTEGER NOT NULL,
    notify_type VARCHAR(255) NOT NULL,
    template_use BOOLEAN NOT NULL,
    target_hashtag VARCHAR(255),
    persona_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (persona_id) REFERENCES personas(id),
    FOREIGN KEY (account_id) REFERENCES twitter_account(account_id)
); 