import requests
import json

def get_word_and_hints(num_hints=3):
    """
    Calls the Hack Club AI API to get a word and hints for a guessing game.
    
    Args:
        num_hints (int): Number of hints to generate (default: 3)
    
    Returns a dictionary with 'word' and 'hints' keys.
    """
    url = "https://ai.hackclub.com/chat/completions"
    
    prompt = f"""You are a word game assistant. Generate a random word and provide exactly {num_hints} single-word hints for guessing that word.

Format your response EXACTLY like this:
WORD: [your_word]
HINTS:
{chr(10).join([f"{i}. [single_word_hint_{i}]" for i in range(1, num_hints + 1)])}

IMPORTANT: Each hint must be exactly ONE WORD only. Make sure the word is a common English word and the single-word hints are helpful but not too obvious."""

    payload = {
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        # Parse the response
        response_data = response.json()
        ai_response = response_data['choices'][0]['message']['content']
        
        # Extract word and hints from the structured response
        lines = ai_response.strip().split('\n')
        word = ""
        hints = []
        
        for line in lines:
            line = line.strip()
            if line.startswith("WORD:"):
                word = line.replace("WORD:", "").strip()
            elif line and any(line.startswith(f"{i}.") for i in range(1, num_hints + 1)):
                hint = line[line.find('.') + 1:].strip()  # Remove number and dot
                # Ensure hint is a single word
                hint = hint.split()[0] if hint.split() else hint
                hints.append(hint)
        
        return {
            "word": word,
            "hints": hints
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Error calling AI API: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Error parsing AI response: {e}")
        return None

if __name__ == "__main__":
    result = get_word_and_hints(5)  # Example with 5 hints
    if result:
        print(f"Word: {result['word']}")
        print(f"Hints: {result['hints']}")
    else:
        print("Failed to get word and hints")