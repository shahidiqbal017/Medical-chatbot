document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const typingIndicator = document.getElementById('typing-indicator');
    
    // Get the API URL from the data attribute set in index.html
    const chatApiUrl = document.body.dataset.chatUrl;
    // If you put it on a different element, adjust the selector:
    // const chatApiUrl = document.querySelector('.chat-app-container').dataset.chatUrl; 

    function getCurrentTime() {
        const now = new Date();
        const hours = now.getHours().toString().padStart(2, '0');
        const minutes = now.getMinutes().toString().padStart(2, '0');
        return `${hours}:${minutes}`;
    }

    function appendMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender + '-message');

        const avatarPlaceholder = document.createElement('div');
        avatarPlaceholder.classList.add('avatar-placeholder');
        if (sender === 'bot') {
            avatarPlaceholder.classList.add('bot-avatar-chat');
            avatarPlaceholder.innerHTML = '<i class="fas fa-robot"></i>';
        } else {
            avatarPlaceholder.classList.add('user-avatar-chat');
            avatarPlaceholder.innerHTML = '<i class="fas fa-user"></i>';
        }

        const messageContentDiv = document.createElement('div');
        messageContentDiv.classList.add('message-content');

        const bubbleDiv = document.createElement('div');
        bubbleDiv.classList.add('message-bubble');
        bubbleDiv.innerHTML = text; 

        const timestampSpan = document.createElement('span');
        timestampSpan.classList.add('timestamp');
        timestampSpan.textContent = getCurrentTime();

        messageContentDiv.appendChild(bubbleDiv);
        messageContentDiv.appendChild(timestampSpan);

        if (sender === 'user') {
            messageDiv.appendChild(messageContentDiv);
            messageDiv.appendChild(avatarPlaceholder);
        } else {
            messageDiv.appendChild(avatarPlaceholder);
            messageDiv.appendChild(messageContentDiv);
        }
        
        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }
    
    const initialBotMessageTimestamp = chatBox.querySelector('.bot-message .timestamp');
    if (initialBotMessageTimestamp) {
        initialBotMessageTimestamp.textContent = getCurrentTime();
    }

    function showTypingIndicator() {
        typingIndicator.style.display = 'flex';
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function hideTypingIndicator() {
        typingIndicator.style.display = 'none';
    }

    function adjustTextareaHeight() {
        userInput.style.height = 'auto';
        userInput.style.height = (userInput.scrollHeight) + 'px';
    }

    userInput.addEventListener('input', () => {
        adjustTextareaHeight();
        sendBtn.disabled = userInput.value.trim() === '';
    });
    sendBtn.disabled = true;

    function sendMessage() {
        const messageText = userInput.value.trim();
        if (messageText === '') return;

        appendMessage(`<p>${messageText.replace(/\n/g, "<br>")}</p>`, 'user'); 
        userInput.value = '';
        sendBtn.disabled = true;
        adjustTextareaHeight();
        showTypingIndicator();

        fetch(chatApiUrl, { // <--- USING THE CORRECT URL NOW
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: messageText })
        })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status} for URL: ${response.url}`); // Log URL
            return response.json();
        })
        .then(data => {
            setTimeout(() => {
                hideTypingIndicator();
                appendMessage(data.reply, 'bot');
            }, 1000 + Math.random() * 1000);
        })
        .catch(error => {
            console.error('Error during fetch:', error); // More detailed error
            hideTypingIndicator();
            appendMessage('<p>Sorry, I encountered an issue reaching the server. Please try again later.</p>', 'bot');
        });
    }

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    adjustTextareaHeight();
});