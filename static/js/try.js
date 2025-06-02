document.addEventListener('DOMContentLoaded', () => {
    const questionForm = document.getElementById('questionForm');
    const questionInput = document.getElementById('questionInput');
    const chatMessages = document.getElementById('chatMessages');
    const historyTable = document.getElementById('historyTable');
    const loadingModal = document.getElementById('loadingModal');
    const deleteModal = document.getElementById('deleteModal');
    const newChatBtn = document.getElementById('newChatBtn');
    const deleteChatBtn = document.getElementById('deleteChatBtn');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
    let currentChatId = null;

    // Load chat history on page load
    loadChatHistory();

    // New Chat Button
    newChatBtn.addEventListener('click', () => {
        currentChatId = null;
        chatMessages.innerHTML = '';
        questionInput.value = '';
        deleteChatBtn.disabled = true;
        
        // Update active state in table
        const rows = historyTable.querySelectorAll('tbody tr');
        rows.forEach(row => row.classList.remove('active'));
    });

    // Delete Chat Button
    deleteChatBtn.addEventListener('click', () => {
        if (currentChatId) {
            deleteModal.classList.add('show');
        }
    });

    // Confirm Delete
    confirmDeleteBtn.addEventListener('click', async () => {
        if (currentChatId) {
            try {
                const response = await fetch(`/api/chat/${currentChatId}`, {
                    method: 'DELETE'
                });

                if (!response.ok) {
                    throw new Error('Failed to delete chat');
                }

                // Clear current chat
                currentChatId = null;
                chatMessages.innerHTML = '';
                questionInput.value = '';
                deleteChatBtn.disabled = true;

                // Update chat history
                loadChatHistory();
            } catch (error) {
                console.error('Error deleting chat:', error);
            }
        }
        deleteModal.classList.remove('show');
    });

    // Cancel Delete
    cancelDeleteBtn.addEventListener('click', () => {
        deleteModal.classList.remove('show');
    });

    // Handle form submission
    questionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = questionInput.value.trim();
        if (!question) return;

        // Show loading modal
        loadingModal.classList.add('show');

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    question,
                    chat_id: currentChatId
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to get response');
            }

            const data = await response.json();
            
            // If this is a new chat, update currentChatId
            if (!currentChatId) {
                currentChatId = data.chat_id;
                // Clear messages for new chat
                chatMessages.innerHTML = '';
            }
            
            // Add new messages to chat
            data.messages.forEach(msg => {
                addMessageToChat(msg, msg.role === 'user');
            });
            
            // Update chat history
            loadChatHistory();
            
            // Clear input
            questionInput.value = '';
        } catch (error) {
            console.error('Error:', error);
            const errorMessage = {
                content: 'Sorry, there was an error processing your question. Please try again.',
                role: 'bot',
                timestamp: new Date().toISOString()
            };
            addMessageToChat(errorMessage, false);
        } finally {
            loadingModal.classList.remove('show');
        }
    });

    // Function to load chat history
    async function loadChatHistory() {
        try {
            const response = await fetch('/api/chats');
            if (!response.ok) {
                throw new Error('Failed to load chat history');
            }

            const chats = await response.json();
            
            // Clear existing table rows
            const tbody = historyTable.querySelector('tbody');
            tbody.innerHTML = '';
            
            // Add chat history rows
            chats.forEach(chat => {
                const date = new Date(chat.timestamp);
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>#${chat.id}</td>
                    <td>${formatDate(date)}</td>
                    <td>${formatTime(date)}</td>
                `;
                
                // Add click event to load chat
                row.addEventListener('click', () => loadChat(chat.id));
                
                // Highlight current chat
                if (chat.id === currentChatId) {
                    row.classList.add('active');
                }
                
                tbody.appendChild(row);
            });

            // Enable/disable delete button based on current chat
            deleteChatBtn.disabled = !currentChatId;
        } catch (error) {
            console.error('Error loading chat history:', error);
        }
    }

    // Function to load a specific chat
    async function loadChat(chatId) {
        try {
            const response = await fetch(`/api/chat/${chatId}`);
            if (!response.ok) {
                throw new Error('Failed to load chat');
            }

            const chatData = await response.json();
            currentChatId = chatId;
            
            // Clear existing messages
            chatMessages.innerHTML = '';
            
            // Add messages to chat
            if (Array.isArray(chatData)) {
                chatData.forEach(msg => {
                    const message = {
                        role: 'user',
                        content: msg.question,
                        timestamp: msg.timestamp
                    };
                    addMessageToChat(message, true);
                    
                    const botMessage = {
                        role: 'bot',
                        content: msg.answer,
                        timestamp: msg.timestamp
                    };
                    addMessageToChat(botMessage, false);
                });
            }
            
            // Update active state in history table
            const rows = historyTable.querySelectorAll('tbody tr');
            rows.forEach(row => row.classList.remove('active'));
            const activeRow = Array.from(rows).find(row => row.cells[0].textContent === `#${chatId}`);
            if (activeRow) {
                activeRow.classList.add('active');
            }

            // Enable delete button
            deleteChatBtn.disabled = false;
        } catch (error) {
            console.error('Error loading chat:', error);
            showNotification('Failed to load chat history', 'error');
        }
    }

    function formatDate(dateString) {
        try {
            const date = new Date(dateString);
            if (isNaN(date.getTime())) {
                return 'Just now';
            }
            return date.toLocaleString();
        } catch (error) {
            console.error('Error formatting date:', error);
            return 'Just now';
        }
    }

    function formatTime(date) {
        if (typeof date === 'string') {
            date = new Date(date);
        }
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    function addMessageToChat(message, isUser = true) {
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = message.content;
        
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = formatTime(new Date(message.timestamp));
        
        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(timeDiv);
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Function to show notification
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Remove notification after 3 seconds
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}); 