# Database Setup Instructions for Imposter Game

## Prerequisites

1. **Install PostgreSQL**
   - macOS: `brew install postgresql`
   - Ubuntu: `sudo apt install postgresql postgresql-contrib`
   - Windows: Download from https://www.postgresql.org/download/

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Database Setup

1. **Start PostgreSQL service**
   ```bash
   # macOS with Homebrew
   brew services start postgresql
   
   # Ubuntu
   sudo service postgresql start
   ```

2. **Create database and user**
   ```bash
   # Access PostgreSQL as postgres user
   sudo -u postgres psql
   
   # In PostgreSQL shell, create database and user
   CREATE DATABASE imposter_game;
   CREATE USER imposter_user WITH ENCRYPTED PASSWORD 'your_password_here';
   GRANT ALL PRIVILEGES ON DATABASE imposter_game TO imposter_user;
   \q
   ```

3. **Create tables using the schema**
   ```bash
   # Run the schema file
   psql -U imposter_user -d imposter_game -f imposter_game_schema.sql
   ```

## Environment Configuration

Set the `DATABASE_URL` environment variable or update the `db_handler.py` file:

```bash
# Option 1: Environment variable
export DATABASE_URL="postgresql://imposter_user:your_password_here@localhost:5432/imposter_game"

# Option 2: Create a .env file
echo "DATABASE_URL=postgresql://imposter_user:your_password_here@localhost:5432/imposter_game" > .env
```

## Testing the Connection

Run the app and check the console output:
```bash
python app.py
```

You should see:
- `✅ Database connected successfully` - Database is working
- `❌ Database connection failed, using in-memory storage` - Fallback mode

## Database Features

When the database is connected, the app will:

- ✅ **Persist lobbies** - Lobbies survive server restarts
- ✅ **Store player data** - Player information and roles
- ✅ **Track games** - Game sessions with words and hints
- ✅ **Record votes** - All voting data for analysis
- ✅ **Save results** - Game outcomes and statistics

## Fallback Mode

If the database is not available, the app automatically falls back to in-memory storage:
- All functionality works as before
- Data is lost when server restarts
- No persistence between sessions

## Useful Database Commands

```sql
-- View all active lobbies
SELECT * FROM lobbies WHERE status = 'waiting' OR status = 'in_progress';

-- View players in a specific lobby
SELECT p.*, l.code FROM players p 
JOIN lobbies l ON p.lobby_id = l.id 
WHERE l.code = 'ABC123';

-- View voting results for a game
SELECT 
    voter.name as voter,
    voted.name as voted_for,
    v.voted_at
FROM votes v
JOIN players voter ON v.voter_id = voter.id
JOIN players voted ON v.voted_player_id = voted.id
WHERE v.game_id = 1;

-- Clean up old lobbies (older than 24 hours)
DELETE FROM lobbies WHERE created_at < NOW() - INTERVAL '24 hours';
```

## Troubleshooting

1. **Connection refused**: Check if PostgreSQL is running
2. **Authentication failed**: Verify username/password
3. **Database does not exist**: Create the database first
4. **Permission denied**: Grant proper privileges to the user
5. **Schema errors**: Make sure the schema file was applied correctly

## Security Notes

- Change default passwords in production
- Use environment variables for sensitive data
- Consider connection pooling for high traffic
- Regular backups recommended for production use
