// Game Landing Page JavaScript

// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Game functions
function startGame() {
    // Add button click animation
    const btn = event.target.closest('.btn-primary');
    btn.style.transform = 'scale(0.95)';
    setTimeout(() => {
        btn.style.transform = '';
    }, 150);

    // Get player name
    const playerName = prompt('Enter your name:');
    if (!playerName || playerName.trim() === '') {
        showNotification('Please enter a valid name!', 'error');
        return;
    }
    
    showNotification('Creating lobby...', 'info');
    createLobby(playerName.trim());
}

function joinGame() {
    // Add button click animation
    const btn = event.target.closest('.btn-secondary');
    btn.style.transform = 'scale(0.95)';
    setTimeout(() => {
        btn.style.transform = '';
    }, 150);

    // Redirect to join page
    window.location.href = '/join';
}

function createLobby(playerName) {
    // Connect to socket and create lobby
    const socket = io();
    
    socket.on('connect', () => {
        socket.emit('create_lobby', {
            player_name: playerName
        });
    });
    
    socket.on('lobby_created', (data) => {
        showNotification('Lobby created successfully!', 'success');
        setTimeout(() => {
            window.location.href = `/lobby/${data.room_code}?name=${encodeURIComponent(data.player_name)}`;
        }, 1000);
    });
    
    socket.on('error', (data) => {
        showNotification('Error: ' + data.message, 'error');
    });
}

// Notification system
function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotification = document.querySelector('.notification');
    if (existingNotification) {
        existingNotification.remove();
    }

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span class="notification-text">${message}</span>
        <button class="notification-close" onclick="closeNotification(this)">&times;</button>
    `;

    // Add notification styles
    notification.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        background: ${type === 'success' ? 'rgba(0, 245, 255, 0.9)' : 
                    type === 'error' ? 'rgba(255, 0, 128, 0.9)' : 
                    'rgba(255, 215, 0, 0.9)'};
        color: #0a0a0f;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        z-index: 10000;
        font-family: 'Rajdhani', sans-serif;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 1rem;
        animation: slideIn 0.3s ease;
        max-width: 300px;
    `;

    // Add animation keyframes
    if (!document.querySelector('#notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
            .notification-close {
                background: none;
                border: none;
                color: inherit;
                font-size: 1.5rem;
                cursor: pointer;
                padding: 0;
                line-height: 1;
            }
        `;
        document.head.appendChild(style);
    }

    // Add to page
    document.body.appendChild(notification);

    // Auto remove after 3 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            closeNotification(notification.querySelector('.notification-close'));
        }
    }, 3000);
}

function closeNotification(closeBtn) {
    const notification = closeBtn.parentNode;
    notification.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 300);
}

// Add parallax effect to floating shapes
function addParallaxEffect() {
    const shapes = document.querySelectorAll('.shape');
    let mouseX = 0;
    let mouseY = 0;

    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX / window.innerWidth;
        mouseY = e.clientY / window.innerHeight;

        shapes.forEach((shape, index) => {
            const speed = (index + 1) * 0.5;
            const x = (mouseX - 0.5) * speed * 50;
            const y = (mouseY - 0.5) * speed * 50;
            
            shape.style.transform = `translate(${x}px, ${y}px)`;
        });
    });
}

// Initialize interactive features when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Add parallax effect
    addParallaxEffect();

    // Add glitch effect to logo periodically
    setInterval(() => {
        const logo = document.querySelector('.logo-text');
        if (logo && Math.random() < 0.1) { // 10% chance every interval
            logo.style.textShadow = '2px 0 #ff0080, -2px 0 #00f5ff';
            setTimeout(() => {
                logo.style.textShadow = '0 0 30px rgba(0, 245, 255, 0.5)';
            }, 100);
        }
    }, 2000);

    // Add typing effect to secret word
    const secretWord = document.querySelector('.secret-word');
    if (secretWord) {
        const words = ['???', 'SECRET', 'HIDDEN', 'MYSTERY', '???'];
        let currentIndex = 0;
        
        setInterval(() => {
            secretWord.style.opacity = '0';
            setTimeout(() => {
                currentIndex = (currentIndex + 1) % words.length;
                secretWord.textContent = words[currentIndex];
                secretWord.style.opacity = '1';
            }, 300);
        }, 3000);
    }

    // Add random impostor glow to different players
    const players = document.querySelectorAll('.player-avatar');
    setInterval(() => {
        // Remove impostor class from all players
        players.forEach(player => player.classList.remove('impostor'));
        
        // Add impostor class to random player
        if (players.length > 0) {
            const randomPlayer = players[Math.floor(Math.random() * players.length)];
            randomPlayer.classList.add('impostor');
        }
    }, 4000);

    // Add scroll-based animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animation = 'fadeInUp 0.6s ease forwards';
            }
        });
    }, observerOptions);

    // Observe elements for scroll animations
    document.querySelectorAll('.step, .feature-card').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        observer.observe(el);
    });

    // Add fadeInUp animation
    if (!document.querySelector('#scroll-animations')) {
        const style = document.createElement('style');
        style.id = 'scroll-animations';
        style.textContent = `
            @keyframes fadeInUp {
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
        `;
        document.head.appendChild(style);
    }
});

// Add keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Press 'S' to start game
    if (e.key.toLowerCase() === 's' && !e.ctrlKey && !e.metaKey) {
        const startBtn = document.querySelector('.btn-primary');
        if (startBtn && document.activeElement.tagName !== 'INPUT') {
            startBtn.click();
        }
    }
    
    // Press 'J' to join game
    if (e.key.toLowerCase() === 'j' && !e.ctrlKey && !e.metaKey) {
        const joinBtn = document.querySelector('.btn-secondary');
        if (joinBtn && document.activeElement.tagName !== 'INPUT') {
            joinBtn.click();
        }
    }
});

// Add dynamic stats counter animation
function animateStats() {
    const stats = document.querySelectorAll('.stat-number');
    stats.forEach((stat, index) => {
        const target = parseInt(stat.textContent.replace(/\D/g, ''));
        let current = 0;
        const increment = target / 100;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            
            // Format the number with original suffix
            const originalText = stat.textContent;
            const suffix = originalText.replace(/[\d]/g, '');
            stat.textContent = Math.floor(current) + suffix;
        }, 20);
    });
}

// Run stats animation when the hero section is visible
const heroObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            animateStats();
            heroObserver.disconnect(); // Run only once
        }
    });
}, { threshold: 0.5 });

document.addEventListener('DOMContentLoaded', () => {
    const heroStats = document.querySelector('.hero-stats');
    if (heroStats) {
        heroObserver.observe(heroStats);
    }
});
