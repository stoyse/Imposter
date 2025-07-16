"""
Database handler for Imposter Game
Handles PostgreSQL connections and operations
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, database_url=None):
        """
        Initialize database connection
        database_url format: postgresql://username:password@localhost:5432/database_name
        """
        self.database_url = database_url or os.getenv('DATABASE_URL', 
            'postgresql://localhost:5432/imposter_game')
        self.connection = None
        
    def connect(self):
        """Establish database connection"""
        try:
            self.connection = psycopg2.connect(
                self.database_url,
                cursor_factory=RealDictCursor
            )
            logger.info("Database connection established")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
    
    def execute_query(self, query, params=None, fetch=False):
        """Execute a query with optional parameters"""
        try:
            if not self.connection:
                self.connect()
                
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                
                if fetch:
                    if fetch == 'one':
                        result = cursor.fetchone()
                    else:
                        result = cursor.fetchall()
                    return result
                else:
                    self.connection.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            if self.connection:
                self.connection.rollback()
            return None if fetch else False
    
    # Lobby Operations
    def create_lobby(self, code, creator_name):
        """Create a new lobby and add the creator as host"""
        try:
            # Create lobby
            lobby_query = """
                INSERT INTO lobbies (code, status) 
                VALUES (%s, 'waiting') 
                RETURNING id
            """
            lobby_result = self.execute_query(lobby_query, (code,), fetch='one')
            
            if not lobby_result:
                return None
                
            lobby_id = lobby_result['id']
            
            # Add creator as host player
            player_query = """
                INSERT INTO players (lobby_id, name, is_host) 
                VALUES (%s, %s, true) 
                RETURNING id
            """
            player_result = self.execute_query(player_query, (lobby_id, creator_name), fetch='one')
            
            if player_result:
                return {
                    'lobby_id': lobby_id,
                    'player_id': player_result['id'],
                    'code': code
                }
            return None
            
        except Exception as e:
            logger.error(f"Create lobby failed: {e}")
            return None
    
    def get_lobby(self, code):
        """Get lobby information by code"""
        query = """
            SELECT * FROM lobbies WHERE code = %s
        """
        return self.execute_query(query, (code,), fetch='one')
    
    def update_lobby_status(self, code, status):
        """Update lobby status"""
        query = """
            UPDATE lobbies SET status = %s WHERE code = %s
        """
        return self.execute_query(query, (status, code))
    
    def delete_lobby(self, code):
        """Delete a lobby and all associated data"""
        query = """
            DELETE FROM lobbies WHERE code = %s
        """
        return self.execute_query(query, (code,))
    
    # Player Operations
    def add_player_to_lobby(self, code, player_name):
        """Add a player to a lobby"""
        try:
            # Get lobby_id
            lobby = self.get_lobby(code)
            if not lobby:
                return None
                
            # Check if player already exists
            existing_query = """
                SELECT id FROM players WHERE lobby_id = %s AND name = %s
            """
            existing = self.execute_query(existing_query, (lobby['id'], player_name), fetch='one')
            
            if existing:
                return {'player_id': existing['id'], 'lobby_id': lobby['id']}
            
            # Add new player
            query = """
                INSERT INTO players (lobby_id, name, is_host) 
                VALUES (%s, %s, false) 
                RETURNING id
            """
            result = self.execute_query(query, (lobby['id'], player_name), fetch='one')
            
            if result:
                return {'player_id': result['id'], 'lobby_id': lobby['id']}
            return None
            
        except Exception as e:
            logger.error(f"Add player failed: {e}")
            return None
    
    def get_lobby_players(self, code):
        """Get all players in a lobby"""
        query = """
            SELECT p.* FROM players p
            JOIN lobbies l ON p.lobby_id = l.id
            WHERE l.code = %s
            ORDER BY p.joined_at
        """
        return self.execute_query(query, (code,), fetch='all')
    
    def remove_player_from_lobby(self, code, player_name):
        """Remove a player from a lobby"""
        query = """
            DELETE FROM players 
            WHERE lobby_id = (SELECT id FROM lobbies WHERE code = %s) 
            AND name = %s
        """
        return self.execute_query(query, (code, player_name))
    
    def update_player_role(self, player_id, is_impostor, role=None):
        """Update player's impostor status and role"""
        query = """
            UPDATE players 
            SET is_impostor = %s, role = %s 
            WHERE id = %s
        """
        return self.execute_query(query, (is_impostor, role, player_id))
    
    # Game Operations
    def create_game(self, code, secret_word, impostor_hint, impostor_count):
        """Create a new game for a lobby"""
        try:
            lobby = self.get_lobby(code)
            if not lobby:
                return None
                
            query = """
                INSERT INTO games (lobby_id, secret_word, impostor_hint, impostor_count)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """
            result = self.execute_query(query, (lobby['id'], secret_word, impostor_hint, impostor_count), fetch='one')
            
            if result:
                # Update lobby status to in_progress
                self.update_lobby_status(code, 'in_progress')
                return result['id']
            return None
            
        except Exception as e:
            logger.error(f"Create game failed: {e}")
            return None
    
    def get_current_game(self, code):
        """Get the current active game for a lobby"""
        query = """
            SELECT g.* FROM games g
            JOIN lobbies l ON g.lobby_id = l.id
            WHERE l.code = %s AND g.ended_at IS NULL
            ORDER BY g.started_at DESC
            LIMIT 1
        """
        return self.execute_query(query, (code,), fetch='one')
    
    def end_game(self, game_id):
        """End a game"""
        query = """
            UPDATE games 
            SET ended_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """
        return self.execute_query(query, (game_id,))
    
    # Voting Operations
    def add_vote(self, game_id, voter_id, voted_player_id):
        """Add a vote (or remove if already exists - toggle behavior)"""
        try:
            # Check if vote already exists
            check_query = """
                SELECT id FROM votes 
                WHERE game_id = %s AND voter_id = %s AND voted_player_id = %s
            """
            existing = self.execute_query(check_query, (game_id, voter_id, voted_player_id), fetch='one')
            
            if existing:
                # Remove existing vote (toggle off)
                delete_query = """
                    DELETE FROM votes 
                    WHERE id = %s
                """
                return self.execute_query(delete_query, (existing['id'],))
            else:
                # Add new vote
                insert_query = """
                    INSERT INTO votes (game_id, voter_id, voted_player_id)
                    VALUES (%s, %s, %s)
                """
                return self.execute_query(insert_query, (game_id, voter_id, voted_player_id))
                
        except Exception as e:
            logger.error(f"Add vote failed: {e}")
            return False
    
    def get_player_votes(self, game_id, voter_id):
        """Get all votes cast by a specific player"""
        query = """
            SELECT p.name FROM votes v
            JOIN players p ON v.voted_player_id = p.id
            WHERE v.game_id = %s AND v.voter_id = %s
        """
        result = self.execute_query(query, (game_id, voter_id), fetch='all')
        return [row['name'] for row in result] if result else []
    
    def get_all_votes(self, game_id):
        """Get all votes for a game"""
        query = """
            SELECT 
                voter.name as voter_name,
                voted.name as voted_name
            FROM votes v
            JOIN players voter ON v.voter_id = voter.id
            JOIN players voted ON v.voted_player_id = voted.id
            WHERE v.game_id = %s
        """
        return self.execute_query(query, (game_id,), fetch='all')
    
    def get_vote_counts(self, game_id):
        """Get vote counts for each player"""
        query = """
            SELECT 
                p.name,
                COUNT(v.id) as vote_count
            FROM players p
            LEFT JOIN votes v ON p.id = v.voted_player_id AND v.game_id = %s
            WHERE p.lobby_id = (SELECT lobby_id FROM games WHERE id = %s)
            GROUP BY p.id, p.name
            ORDER BY vote_count DESC
        """
        return self.execute_query(query, (game_id, game_id), fetch='all')
    
    # Game Results
    def save_game_result(self, game_id, winner, revealed_impostors):
        """Save game results"""
        try:
            # Convert list to JSON string
            impostors_json = json.dumps(revealed_impostors) if isinstance(revealed_impostors, list) else revealed_impostors
            
            query = """
                INSERT INTO game_results (game_id, winner, revealed_impostors)
                VALUES (%s, %s, %s)
            """
            result = self.execute_query(query, (game_id, winner, impostors_json))
            
            if result:
                # End the game
                self.end_game(game_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Save game result failed: {e}")
            return False
    
    def get_game_result(self, game_id):
        """Get game results"""
        query = """
            SELECT * FROM game_results WHERE game_id = %s
        """
        return self.execute_query(query, (game_id,), fetch='one')
    
    # Utility Functions
    def get_player_by_name(self, code, player_name):
        """Get player by name in a specific lobby"""
        query = """
            SELECT p.* FROM players p
            JOIN lobbies l ON p.lobby_id = l.id
            WHERE l.code = %s AND p.name = %s
        """
        return self.execute_query(query, (code, player_name), fetch='one')
    
    def get_impostors(self, code):
        """Get all impostors in a lobby"""
        query = """
            SELECT p.name FROM players p
            JOIN lobbies l ON p.lobby_id = l.id
            WHERE l.code = %s AND p.is_impostor = true
        """
        result = self.execute_query(query, (code,), fetch='all')
        return [row['name'] for row in result] if result else []
    
    def cleanup_old_lobbies(self, hours=24):
        """Clean up lobbies older than specified hours"""
        query = """
            DELETE FROM lobbies 
            WHERE created_at < NOW() - INTERVAL '%s hours'
        """
        return self.execute_query(query, (hours,))

# Singleton instance
db = DatabaseHandler()
