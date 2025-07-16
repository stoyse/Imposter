-- imposter_game_schema.sql
-- PostgreSQL schema for Imposter Game

-- Table: lobbies
CREATE TABLE lobbies (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'waiting' -- waiting, in_progress, finished
);

-- Table: players
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    lobby_id INTEGER REFERENCES lobbies(id) ON DELETE CASCADE,
    name VARCHAR(32) NOT NULL,
    is_impostor BOOLEAN DEFAULT FALSE,
    role VARCHAR(20),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lobby_id, name)
);

-- Table: games (one per round)
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    lobby_id INTEGER REFERENCES lobbies(id) ON DELETE CASCADE,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    secret_word VARCHAR(64),
    impostor_hint VARCHAR(128),
    impostor_count INTEGER DEFAULT 1
);

-- Table: votes
CREATE TABLE votes (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    voter_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    voted_player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, voter_id, voted_player_id)
);

-- Table: game_results
CREATE TABLE game_results (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    winner VARCHAR(20), -- 'impostors' or 'innocents'
    revealed_impostors TEXT, -- comma-separated names or JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_lobby_code ON lobbies(code);
CREATE INDEX idx_votes_game_id ON votes(game_id);
CREATE INDEX idx_players_lobby_id ON players(lobby_id);

-- Optionally, you can use JSONB for storing flexible data (e.g. revealed_impostors)
-- and add more columns as needed for analytics or game history.
