function addMessage(sender, text, isApi = false) {
  const chatBox = document.getElementById("chat-box");
  const messageWrapper = document.createElement("div");
  messageWrapper.classList.add("message-wrapper", sender);

  const avatar = document.createElement("div");
  avatar.classList.add("avatar");
  avatar.innerText = sender === "user" ? "😎" : "🤖";

  const messageDiv = document.createElement("div");
  messageDiv.classList.add("message", sender);
  
  if (isApi) {
    try {
      const data = typeof text === 'string' ? JSON.parse(text) : text;
      
      if (data.type === 'link') {
        const linkContainer = document.createElement('div');
        linkContainer.classList.add('link-container');
        
        if (data.message) {
          const messageText = document.createElement('div');
          messageText.classList.add('link-message');
          messageText.innerHTML = data.message.replace(/\n/g, '<br>');
          linkContainer.appendChild(messageText);
        }
        
        const buttonWrapper = document.createElement('div');
        buttonWrapper.classList.add('link-button-wrapper');
        
        const linkButton = document.createElement('a');
        linkButton.href = data.url;
        linkButton.target = '_blank'; 
        linkButton.rel = 'noopener noreferrer'; 
        linkButton.classList.add('link-button');
        linkButton.innerHTML = `🔗 ${data.title}`;
        
        buttonWrapper.appendChild(linkButton);
        linkContainer.appendChild(buttonWrapper);
        
        messageDiv.appendChild(linkContainer);
      } else {
        messageDiv.innerHTML = `<div class="api-response">
          <div class="api-content">${typeof text === 'string' ? text.replace(/\n/g, '<br>') : JSON.stringify(text, null, 2)}</div>
        </div>`;
      }
    } catch {
      messageDiv.innerHTML = `<div class="api-response">
        <div class="api-content">${text.replace(/\n/g, '<br>')}</div>
      </div>`;
    }
  } else {
    messageDiv.textContent = text;
  }

  messageWrapper.appendChild(avatar);
  messageWrapper.appendChild(messageDiv);
  chatBox.appendChild(messageWrapper);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function sendMessage() {
  const input = document.getElementById("user-input");
  const message = input.value.trim();
  if (!message) return;

  addMessage("user", message);
  input.value = "";
  showTyping();

  fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message })
  })
    .then(res => res.json())
    .then(data => {
      removeTyping();
      if (data.type === "chat") {
        addMessage("bot", data.result);
      } else if (data.type === "api") {
        addMessage("bot", data.result, true);
      } else if (data.type === "payslip_button") {
        const chatBox = document.getElementById("chat-box");
        const messageWrapper = document.createElement("div");
        messageWrapper.classList.add("message-wrapper", "bot");

        const avatar = document.createElement("div");
        avatar.classList.add("avatar");
        avatar.innerText = "🤖";

        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message", "bot");

        const linkContainer = document.createElement('div');
        linkContainer.classList.add('link-container');
        
        const messageText = document.createElement('div');
        messageText.classList.add('link-message');
        messageText.textContent = data.result.message;
        linkContainer.appendChild(messageText);
        
        const buttonWrapper = document.createElement('div');
        buttonWrapper.classList.add('link-button-wrapper');
        
        const linkButton = document.createElement('a');
        linkButton.href = data.result.url;
        linkButton.target = '_blank'; 
        linkButton.rel = 'noopener noreferrer'; 
        linkButton.classList.add('link-button');
        linkButton.innerHTML = data.result.button_text;
        
        buttonWrapper.appendChild(linkButton);
        linkContainer.appendChild(buttonWrapper);
        
        messageDiv.appendChild(linkContainer);
        messageWrapper.appendChild(avatar);
        messageWrapper.appendChild(messageDiv);
        chatBox.appendChild(messageWrapper);
        chatBox.scrollTop = chatBox.scrollHeight;
      } else {
        addMessage("bot", "🤖 Không rõ phản hồi từ server.");
      }
    })
    .catch(() => {
      removeTyping();
      addMessage("bot", "⚠️ Lỗi kết nối đến server.");
    });
}

function showTyping() {
  const typingDiv = document.createElement("div");
  typingDiv.classList.add("message-wrapper", "bot");
  typingDiv.id = "typing-indicator";

  typingDiv.innerHTML = `
    <div class="avatar">🤖</div>
    <div class="message bot typing"><span class="dot-flashing"></span> Đang trả lời...</div>
  `;

  document.getElementById("chat-box").appendChild(typingDiv);
  document.getElementById("chat-box").scrollTop = document.getElementById("chat-box").scrollHeight;
}


function removeTyping() {
  const typing = document.getElementById("typing-indicator");
  if (typing) typing.remove();
}

document.getElementById("user-input").addEventListener("keydown", function (e) {
  if (e.key === "Enter") sendMessage();
});

function initChat() {
  const welcomeMessages = [
    "Xin chào! Tôi là trợ lý AI của SapotaCorp. Tôi có thể giúp gì cho bạn?"
  ];
  
  setTimeout(() => {
    welcomeMessages.forEach((msg, index) => {
      setTimeout(() => {
        addMessage("bot", msg);
      }, index * 800);
    });
  }, 500);

  // Add event listeners to suggestion buttons
  document.querySelectorAll('.suggestion-button').forEach(button => {
    button.addEventListener('click', () => {
      const userInput = document.getElementById('user-input');
      userInput.value = button.getAttribute('data-text');
      // Automatically send the message after filling the input
      sendMessage();
    });
  });
}

function toggleChat() {
  const chatContainer = document.querySelector(".chat-container");
  chatContainer.style.display = (chatContainer.style.display === "none" || chatContainer.style.display === "") ? "flex" : "none";
  if (chatContainer.style.display === "flex") {
  setTimeout(() => {
    const chatBox = document.getElementById("chat-box");
    if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
  }, 300);
}
}

window.addEventListener("load", initChat);


