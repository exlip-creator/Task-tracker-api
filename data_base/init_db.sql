CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    completed BOOLEAN DEFAULT FALSE
);

INSERT INTO tasks (title, description) VALUES
('Learn Python', "Don't forget about numpy"),
('Buy milk'),
('Go to gym', 'Today I need to do 50 push ups');