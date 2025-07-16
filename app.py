from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string
import sys
import os
import threading
import time

# Add the utils directory to the path so we can import the AI function
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from utils.ai_word_generator import get_word_and_hints
from db_handler import db

app = Flask(__name__, template_folder='template')
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize database connection
try:
    if db.connect():
        print("✅ Database connected successfully")
        # Enable database mode
        USE_DATABASE = True
    else:
        print("❌ Database connection failed, using in-memory storage")
        USE_DATABASE = False
except Exception as e:
    print(f"❌ Database error: {e}, using in-memory storage")
    USE_DATABASE = False

# Store active lobbies (fallback when database is not available)
lobbies = {}

# --- Voting Timer for Impostor Voting (Game Phase) ---
voting_timers = {}

def start_game_voting_timer(room_code, duration=180):
    def timer_thread():
        if room_code not in lobbies:
            return
        lobby = lobbies[room_code]
        lobby['voting_end_time'] = time.time() + duration
        for i in range(duration, 0, -1):
            if room_code not in lobbies:
                return
            left = int(lobby['voting_end_time'] - time.time())
            if left < 0:
                left = 0
            socketio.emit('voting_timer_update', {'seconds_left': left}, room=room_code)
            if left == 0:
                break
            time.sleep(1)
        # Voting ended
        lobby['voting_ended'] = True
        # Reveal impostors to all
        impostors = [p['name'] for p in lobby['players'] if p.get('is_impostor')]
        socketio.emit('impostors_revealed', {'impostors': impostors}, room=room_code)
        
        # Determine winner (simplified logic)
        # In a real game, you'd have more complex win conditions
        winner = 'impostors'  # Default assumption
        
        # Save game results to database
        if USE_DATABASE and lobby.get('db_game_id'):
            result_saved = db.save_game_result(lobby['db_game_id'], winner, impostors)
            if result_saved:
                print(f"✅ Game results saved to database")
            else:
                print("❌ Failed to save game results")
        
        # Send voting results to all clients (server-side)
        votes = lobby.get('impostor_votes_final', {})
        selected_imposters = lobby.get('selected_imposters', 1)
        socketio.emit('voting_results', {
            'votes': votes, 
            'impostors': impostors,
            'total_allowed_votes': selected_imposters
        }, room=room_code)
    t = threading.Thread(target=timer_thread, daemon=True)
    t.start()
    voting_timers[room_code] = t

def generate_room_code():
    """Generate a 6-character room code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.route('/')
def index():
    return render_template('index_new.html')

@app.route('/about')
def about():
    return render_template('about_new.html')

@app.route('/lobby/<room_code>')
def lobby(room_code):
    return render_template('lobby_new.html', room_code=room_code)

@app.route('/join')
def join():
    return render_template('join_new.html')

@app.route('/debug/lobbies')
def debug_lobbies():
    return {'active_lobbies': list(lobbies.keys()), 'lobby_details': lobbies}

@app.route('/debug')
def debug():
    return render_template('debug_new.html', lobbies=lobbies)

@app.route('/game/<room_code>')
def game(room_code):
    return render_template('game_new.html', room_code=room_code)

@app.route('/imposter-selection/<room_code>')
def imposter_selection(room_code):
    if room_code not in lobbies:
        return redirect('/')
    
    lobby = lobbies[room_code]
    
    # Initialize voting if not started
    if 'countdown_started' not in lobby:
        lobby['countdown_started'] = True
        # Start countdown timer
        start_countdown_timer(room_code)
    
    return render_template('imposter_selection.html', 
                         room_code=room_code,
                         max_imposters=len(lobby['players']) - 1,
                         player_count=len(lobby['players']))

@app.route('/debug/lobby/<room_code>')
def debug_lobby(room_code):
    if room_code in lobbies:
        lobby = lobbies[room_code]
        return {
            'room_code': room_code,
            'status': lobby.get('status', 'unknown'),
            'players': lobby.get('players', []),
            'selected_imposters': lobby.get('selected_imposters'),
            'roles_assigned': lobby.get('roles_assigned', False),
            'votes': lobby.get('votes', {})
        }
    else:
        return {'error': 'Lobby not found'}, 404

@socketio.on('create_lobby')
def handle_create_lobby(data):
    room_code = generate_room_code()
    player_name = data.get('player_name', 'Anonymous')
    
    if USE_DATABASE:
        # Use database
        result = db.create_lobby(room_code, player_name)
        if result:
            # Also store in memory for compatibility
            lobbies[room_code] = {
                'host': request.sid,
                'players': [{'id': request.sid, 'name': player_name, 'ready': False}],
                'status': 'waiting',
                'db_lobby_id': result['lobby_id']
            }
            join_room(room_code)
            print(f"✅ Lobby created in DB: {room_code} by {player_name}")
            emit('lobby_created', {'room_code': room_code, 'player_name': player_name})
        else:
            emit('error', {'message': 'Failed to create lobby'})
    else:
        # Fallback to memory storage
        lobbies[room_code] = {
            'host': request.sid,
            'players': [{'id': request.sid, 'name': player_name, 'ready': False}],
            'status': 'waiting'
        }
        join_room(room_code)
        print(f"Lobby created: {room_code} by {player_name}")
        emit('lobby_created', {'room_code': room_code, 'player_name': player_name})
    
    print(f"Active lobbies: {list(lobbies.keys())}")

@socketio.on('join_lobby')
def handle_join_lobby(data):
    room_code = data.get('room_code', '').upper()
    player_name = data.get('player_name', 'Anonymous')
    
    print(f"Attempting to join lobby: {room_code}")
    print(f"Available lobbies: {list(lobbies.keys())}")
    print(f"Player SID: {request.sid}")
    
    if USE_DATABASE:
        # Check database first
        lobby_data = db.get_lobby(room_code)
        if not lobby_data:
            print(f"Lobby {room_code} not found in DB!")
            emit('error', {'message': 'Lobby not found. Please check the room code.'})
            return
        
        # Add player to database
        player_result = db.add_player_to_lobby(room_code, player_name)
        if not player_result:
            emit('error', {'message': 'Failed to join lobby'})
            return
        
        # Get updated player list from database
        db_players = db.get_lobby_players(room_code)
        players_list = [{'id': request.sid if p['name'] == player_name else 'db_player', 
                        'name': p['name'], 'ready': False, 'is_host': p['is_host']} 
                       for p in db_players]
        
        # Update in-memory lobby
        if room_code not in lobbies:
            lobbies[room_code] = {
                'host': None,
                'players': [],
                'status': lobby_data['status']
            }
        
        lobby = lobbies[room_code]
        lobby['players'] = players_list
        
        # Set host if this is the host player
        for player in players_list:
            if player.get('is_host') and player['name'] == player_name:
                lobby['host'] = request.sid
                player['id'] = request.sid
                break
        
        # Update current player's session ID
        for player in lobby['players']:
            if player['name'] == player_name:
                player['id'] = request.sid
                break
                
    else:
        # Fallback to memory storage
        if room_code not in lobbies:
            print(f"Lobby {room_code} not found!")
            emit('error', {'message': 'Lobby not found. Please check the room code.'})
            return
        
        lobby = lobbies[room_code]
        
        # Check if player already in lobby by name (in case of reconnect)
        existing_player = None
        for player in lobby['players']:
            if player['name'] == player_name:
                existing_player = player
                break
        
        if existing_player:
            # Update the player's session ID (reconnect scenario)
            existing_player['id'] = request.sid
            print(f"Player {player_name} reconnected to lobby {room_code}")
        else:
            # Add new player to lobby
            lobby['players'].append({'id': request.sid, 'name': player_name, 'ready': False})
            print(f"Player {player_name} joined lobby {room_code}")
    
    join_room(room_code)
    
    # Notify all players in the room
    socketio.emit('player_joined', {
        'player_name': player_name,
        'players': lobby['players'],
        'player_count': len(lobby['players'])
    }, room=room_code)
    
    emit('lobby_joined', {'room_code': room_code, 'players': lobby['players']})

@socketio.on('leave_lobby')
def handle_leave_lobby(data):
    room_code = data.get('room_code')
    
    if room_code in lobbies:
        lobby = lobbies[room_code]
        # Remove player from lobby
        lobby['players'] = [p for p in lobby['players'] if p['id'] != request.sid]
        
        leave_room(room_code)
        
        # If lobby is empty, delete it
        if not lobby['players']:
            del lobbies[room_code]
        else:
            # If host left, assign new host
            if lobby['host'] == request.sid and lobby['players']:
                lobby['host'] = lobby['players'][0]['id']
            
            # Notify remaining players
            socketio.emit('player_left', {
                'players': lobby['players'],
                'player_count': len(lobby['players'])
            }, room=room_code)

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    # Don't immediately remove players - they might be navigating between pages
    # We'll handle this with explicit leave_lobby events instead

@socketio.on('check_lobby')
def handle_check_lobby(data):
    room_code = data.get('room_code', '').upper()
    print(f"Checking lobby: {room_code}")
    print(f"Available lobbies: {list(lobbies.keys())}")
    
    if USE_DATABASE:
        lobby_data = db.get_lobby(room_code)
        if lobby_data:
            players = db.get_lobby_players(room_code)
            emit('lobby_exists', {'exists': True, 'players': len(players)})
        else:
            emit('lobby_exists', {'exists': False})
    else:
        if room_code in lobbies:
            emit('lobby_exists', {'exists': True, 'players': len(lobbies[room_code]['players'])})
        else:
            emit('lobby_exists', {'exists': False})

@socketio.on('player_ready')
def handle_player_ready(data):
    room_code = data.get('room_code', '').upper()
    ready_status = data.get('ready', False)
    
    print(f"Player {request.sid} ready status: {ready_status} in lobby {room_code}")
    
    if room_code not in lobbies:
        emit('error', {'message': 'Lobby not found'})
        return
    
    lobby = lobbies[room_code]
    
    # Update player ready status
    for player in lobby['players']:
        if player['id'] == request.sid:
            player['ready'] = ready_status
            print(f"Updated {player['name']} ready status to {ready_status}")
            break
    
    # Check if all players are ready
    all_ready = all(player['ready'] for player in lobby['players'])
    ready_count = sum(1 for player in lobby['players'] if player['ready'])
    
    print(f"Ready players: {ready_count}/{len(lobby['players'])}, All ready: {all_ready}")
    
    # Notify all players in the room about ready status
    socketio.emit('ready_status_update', {
        'players': lobby['players'],
        'ready_count': ready_count,
        'total_players': len(lobby['players']),
        'all_ready': all_ready
    }, room=room_code)
    
    # If all players are ready and we have at least 3 players, start the game
    if all_ready and len(lobby['players']) >= 3:
        lobby['status'] = 'starting'
        socketio.emit('redirect_to_selection', {
            'room_code': room_code
        }, room=room_code)

@socketio.on('start_game')
def handle_start_game(data):
    room_code = data.get('room_code')
    
    if room_code not in lobbies:
        emit('error', {'message': 'Lobby not found'})
        return
    
    lobby = lobbies[room_code]
    
    # Check if we have enough players
    if len(lobby['players']) < 3:
        emit('error', {'message': 'Need at least 3 players to start'})
        return
    
    # Check if all players are ready
    if not all(player.get('ready', False) for player in lobby['players']):
        emit('error', {'message': 'Not all players are ready'})
        return
    
    # Start imposter selection countdown
    lobby['status'] = 'imposter_selection'
    lobby['countdown'] = 10
    lobby['imposter_votes'] = {}  # player_id: vote_count
    
    max_imposters = len(lobby['players']) - 1
    
    # Initialize vote counts for each possible number of imposters
    for i in range(1, max_imposters + 1):
        lobby['imposter_votes'][i] = 0
    
    socketio.emit('imposter_selection_started', {
        'countdown': 10,
        'max_imposters': max_imposters,
        'player_count': len(lobby['players'])
    }, room=room_code)
    
    # Start countdown
    start_imposter_countdown(room_code)

def start_imposter_countdown(room_code):
    """Start the imposter selection countdown"""
    if room_code not in lobbies:
        return
    
    lobby = lobbies[room_code]
    
    def countdown_tick():
        if room_code not in lobbies or lobby['status'] != 'imposter_selection':
            return
        
        lobby['countdown'] -= 1
        
        socketio.emit('countdown_update', {
            'countdown': lobby['countdown'],
            'votes': lobby['imposter_votes']
        }, room=room_code)
        
        if lobby['countdown'] <= 0:
            # Time's up, determine imposter count and start game
            finalize_imposter_selection(room_code)
        else:
            # Schedule next tick
            socketio.start_background_task(lambda: socketio.sleep(1) or countdown_tick())
    
    # Start the countdown
    socketio.start_background_task(lambda: socketio.sleep(1) or countdown_tick())

@socketio.on('vote_imposter_count')
def handle_vote_imposter_count(data):
    room_code = data.get('room_code')
    imposter_count = data.get('imposter_count')
    
    if room_code not in lobbies:
        emit('error', {'message': 'Lobby not found'})
        return
    
    lobby = lobbies[room_code]
    
    # Initialize votes if not exists
    if 'votes' not in lobby:
        lobby['votes'] = {}
    
    # Record the vote
    lobby['votes'][request.sid] = imposter_count
    
    print(f"Vote recorded: {imposter_count} imposters from {request.sid}")
    # Don't emit live vote updates - keep voting secret

def start_countdown_timer(room_code):
    """Start the 10-second countdown for imposter selection"""
    import time
    import threading
    
    def countdown():
        if room_code not in lobbies:
            return
            
        lobby = lobbies[room_code]
        
        for i in range(10, 0, -1):
            if room_code not in lobbies:
                break
            
            # Send countdown update without vote counts
            socketio.emit('countdown_update', {
                'countdown': i
            }, room=room_code)
            
            time.sleep(1)
        
        # Countdown finished - determine winner and start game
        if room_code in lobbies:
            finalize_imposter_selection(room_code)
    
    # Start countdown in background thread
    threading.Thread(target=countdown, daemon=True).start()

def finalize_imposter_selection(room_code):
    """Finalize the imposter selection and randomly assign imposters"""
    if room_code not in lobbies:
        return
    
    lobby = lobbies[room_code]
    
    # Count final votes
    vote_counts = {}
    if 'votes' in lobby:
        for vote in lobby['votes'].values():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1
    
    # Determine winner (most votes, default to 1 if no votes)
    if vote_counts:
        selected_imposters = max(vote_counts.keys(), key=lambda k: vote_counts[k])
    else:
        selected_imposters = 1
    
    # Randomly select imposters from players
    import random
    players = lobby['players'].copy()
    random.shuffle(players)
    
    # Assign roles
    impostor_count = 0
    for i, player in enumerate(players):
        if i < selected_imposters:
            player['role'] = 'impostor'
            player['is_impostor'] = True
            impostor_count += 1
        else:
            player['role'] = 'innocent'
            player['is_impostor'] = False

    # Generate word and hints using AI
    print(f"Generating word and {selected_imposters} hints for {selected_imposters} impostors...")
    word_data = get_word_and_hints(selected_imposters)

    if word_data and word_data.get('word') and word_data.get('hints') and len(word_data['hints']) >= selected_imposters:
        secret_word = word_data['word']
        impostor_hints = word_data['hints']
        print(f"Generated word: {secret_word}")
        print(f"Generated hints: {impostor_hints}")
        
        # Create game record in database
        if USE_DATABASE:
            game_id = db.create_game(room_code, secret_word, ', '.join(impostor_hints), selected_imposters)
            if game_id:
                lobby['db_game_id'] = game_id
                print(f"✅ Game created in DB with ID: {game_id}")
                
                # Update player roles in database
                for player in players:
                    player_data = db.get_player_by_name(room_code, player['name'])
                    if player_data:
                        db.update_player_role(player_data['id'], player['is_impostor'], player['role'])
            else:
                print("❌ Failed to create game in database")
        
        # Assign hints to impostors and word to innocents
        impostor_index = 0
        for player in players:
            if player['is_impostor']:
                player['hint'] = impostor_hints[impostor_index]
                impostor_index += 1
            else:
                player['word'] = secret_word
        lobby['secret_word'] = secret_word
        lobby['impostor_hints'] = impostor_hints
    else:
        # Fallback if AI fails
        print("AI word generation failed, using fallback")
        secret_word = "FALLBACK"
        lobby['secret_word'] = secret_word
        for player in players:
            if player['is_impostor']:
                player['hint'] = "MYSTERY"
            else:
                player['word'] = secret_word
    
    lobby['selected_imposters'] = selected_imposters
    lobby['status'] = 'in_game'
    lobby['roles_assigned'] = True
    
    # Calculate total votes for display
    total_votes = len(lobby.get('votes', {}))
    
    print(f"Roles assigned for room {room_code}:")
    for player in players:
        print(f"  {player['name']}: {player['role']}")
    
    # Send final voting result
    socketio.emit('voting_finished', {
        'result': {
            'selected_count': selected_imposters,
            'total_votes': total_votes
        }
    }, room=room_code)
    
    # Wait 2 seconds then send game starting message
    def send_game_starting():
        import time
        time.sleep(2)
        socketio.emit('game_starting', {
            'message': f'Game starting with {selected_imposters} imposter{"s" if selected_imposters > 1 else ""}!',
            'selected_imposters': selected_imposters
        }, room=room_code)
        
        # Wait another 3 seconds then redirect to game and assign roles
        time.sleep(3)
        
        # Send role information to each player individually
        for player in players:
            print(f"Sending role_assigned to player {player['name']} (ID: {player['id']}): {player['role']}")
            # Send word to innocents, hint to impostors
            socketio.emit('role_assigned', {
                'your_role': player['role'],
                'is_impostor': player['is_impostor'],
                'total_impostors': selected_imposters,
                'total_players': len(players),
                'word': player.get('word', None),
                'hint': player.get('hint', None)
            }, to=player['id'])
        
        # Redirect to game
        socketio.emit('redirect_to_game', {
            'room_code': room_code
        }, room=room_code)

        # Start voting timer for the game phase (impostor voting)
        start_game_voting_timer(room_code, duration=180)

    import threading
    threading.Thread(target=send_game_starting, daemon=True).start()

@socketio.on('join_game')
def handle_join_game(data):
    room_code = data.get('room_code', '').upper()
    player_name = data.get('player_name', 'Anonymous')
    
    print(f"Player {player_name} joining game room: {room_code}")
    
    if room_code not in lobbies:
        emit('error', {'message': 'Game room not found'})
        return
    
    lobby = lobbies[room_code]
    
    # Check if player is in the lobby
    player_found = False
    for player in lobby['players']:
        if player['name'] == player_name:
            player_found = True
            # Update their session ID if needed
            player['id'] = request.sid
            break
    
    if not player_found:
        emit('error', {'message': 'You are not part of this game'})
        return
    
    # Join the room
    join_room(room_code)
    print(f"Player {player_name} joined game room {room_code}")
    
    # Send current game state
    emit('game_joined', {
        'room_code': room_code,
        'status': lobby.get('status', 'waiting'),
        'players': lobby['players'],
        'voting_end_time': lobby.get('voting_end_time'),
        'voting_ended': lobby.get('voting_ended', False)
    })
    
    # If roles are already assigned, send role immediately
    if lobby.get('roles_assigned', False):
        print(f"Roles already assigned, sending role to {player_name}")
        for player in lobby['players']:
            if player['id'] == request.sid:
                print(f"Found player {player['name']}, sending role: {player.get('role', 'unknown')}")
                emit('role_assigned', {
                    'your_role': player['role'],
                    'is_impostor': player.get('is_impostor', False),
                    'total_impostors': lobby.get('selected_imposters', 1),
                    'total_players': len(lobby['players']),
                    'word': player.get('word', None),
                    'hint': player.get('hint', None)
                })
                break
    else:
        print(f"Roles not yet assigned for room {room_code}")
    
    # Update other players about current players in game
    socketio.emit('game_players_update', {
        'players': lobby['players']
    }, room=room_code)

# --- Socket event to get voting timer (for reconnects/refresh) ---
@socketio.on('get_voting_timer')
def handle_get_voting_timer(data):
    room_code = data.get('room_code', '').upper()
    if room_code not in lobbies:
        emit('voting_timer_update', {'seconds_left': 0})
        return
    lobby = lobbies[room_code]
    if 'voting_end_time' in lobby:
        left = int(lobby['voting_end_time'] - time.time())
        if left < 0:
            left = 0
        emit('voting_timer_update', {'seconds_left': left, 'voting_ended': lobby.get('voting_ended', False)})
    else:
        emit('voting_timer_update', {'seconds_left': 0, 'voting_ended': True})

@socketio.on('vote_impostor')
def handle_vote_impostor(data):
    room_code = data.get('room_code', '').upper()
    voted_player = data.get('voted_player')
    voter_sid = request.sid
    print(f"Received impostor vote in {room_code}: {voter_sid} voted for {voted_player}")
    
    if room_code not in lobbies:
        emit('error', {'message': 'Lobby not found'})
        return
    
    lobby = lobbies[room_code]
    
    if 'impostor_votes_final' not in lobby:
        lobby['impostor_votes_final'] = {}
    
    # Find voter name
    voter_name = None
    for p in lobby['players']:
        if p['id'] == voter_sid:
            voter_name = p['name']
            break
    
    if not voter_name:
        emit('error', {'message': 'Voter not found in lobby'})
        return
    
    # Prevent self-vote
    if voted_player == voter_name:
        emit('error', {'message': 'Du kannst nicht für dich selbst stimmen.'})
        return
    
    # Only allow voting if timer not ended
    if lobby.get('voting_ended'):
        emit('error', {'message': 'Die Abstimmung ist beendet.'})
        return

    # Get the number of imposters to know how many votes are allowed
    selected_imposters = lobby.get('selected_imposters', 1)
    
    # Initialize player's votes if not already done
    if voter_name not in lobby['impostor_votes_final']:
        lobby['impostor_votes_final'][voter_name] = []
    
    # Check if player already voted for this person
    if voted_player in lobby['impostor_votes_final'][voter_name]:
        # Remove vote if already voted for this player (toggle)
        lobby['impostor_votes_final'][voter_name].remove(voted_player)
        print(f"{voter_name} removed vote for {voted_player}")
        
        # Update database if available
        if USE_DATABASE:
            game = db.get_current_game(room_code)
            if game:
                voter_data = db.get_player_by_name(room_code, voter_name)
                voted_data = db.get_player_by_name(room_code, voted_player)
                if voter_data and voted_data:
                    db.add_vote(game['id'], voter_data['id'], voted_data['id'])  # This will remove the vote (toggle)
        
        # Return current votes to the player
        emit('vote_status_update', {
            'your_votes': lobby['impostor_votes_final'][voter_name],
            'votes_left': selected_imposters - len(lobby['impostor_votes_final'][voter_name])
        })
        return
    
    # Check if player has already used all their votes
    if len(lobby['impostor_votes_final'][voter_name]) >= selected_imposters:
        emit('error', {'message': f'Du hast bereits {selected_imposters} Stimmen abgegeben. Entferne eine Stimme, um für jemand anderen zu stimmen.'})
        return
    
    # Add vote
    lobby['impostor_votes_final'][voter_name].append(voted_player)
    print(f"Current impostor votes: {lobby['impostor_votes_final']}")
    
    # Update database if available
    if USE_DATABASE:
        game = db.get_current_game(room_code)
        if game:
            voter_data = db.get_player_by_name(room_code, voter_name)
            voted_data = db.get_player_by_name(room_code, voted_player)
            if voter_data and voted_data:
                db.add_vote(game['id'], voter_data['id'], voted_data['id'])
    
    # Return current votes to the player
    emit('vote_status_update', {
        'your_votes': lobby['impostor_votes_final'][voter_name],
        'votes_left': selected_imposters - len(lobby['impostor_votes_final'][voter_name])
    })

if __name__ == '__main__':
    print('Starting Imposter app...')
    socketio.run(app, debug=True, host="0.0.0.0", port=9831)