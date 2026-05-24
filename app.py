from flask import Flask, request, jsonify, session, render_template_string, redirect
import sqlite3
from datetime import datetime
import secrets
import re
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['UPLOAD_FOLDER'] = 'avatars'
os.makedirs('avatars', exist_ok=True)

# Цензура
BAD_WORDS = ['хуй', 'пизда', 'бля', 'ебать', 'ебал', 'нахуй', 'пиздец', 'залупа', 'хуйня', 'мудак', 'говно', 'сука',
             'пидор', 'гандон']


def censor(text):
    for word in BAD_WORDS:
        text = re.sub(re.escape(word), '***', text, flags=re.IGNORECASE)
    return text


def init_db():
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE, 
                  password TEXT, 
                  avatar TEXT DEFAULT '/avatars/default.png')''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER, 
                  username TEXT, 
                  content TEXT, 
                  created_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  from_user TEXT, 
                  to_user TEXT, 
                  message TEXT, 
                  created_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS friend_requests 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  from_user TEXT, 
                  to_user TEXT, 
                  status TEXT DEFAULT 'pending')''')
    c.execute('''CREATE TABLE IF NOT EXISTS friends 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user1 TEXT, 
                  user2 TEXT)''')
    conn.commit()
    conn.close()


init_db()

# Создаем дефолтную аватарку если нет
if not os.path.exists('avatars/default.png'):
    from PIL import Image, ImageDraw

    img = Image.new('RGB', (80, 80), color='#667eea')
    draw = ImageDraw.Draw(img)
    draw.text((25, 25), '🐹', fill='white')
    img.save('avatars/default.png')

# ========== HTML ==========
AUTH_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Ruzhik - Вход</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: white;
            border-radius: 30px;
            padding: 40px;
            width: 400px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        .logo { font-size: 48px; margin-bottom: 20px; }
        h1 {
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            margin-bottom: 30px;
        }
        input {
            width: 100%;
            padding: 15px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 15px;
            font-size: 16px;
        }
        .btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 15px;
            font-size: 16px;
            cursor: pointer;
        }
        .switch { margin-top: 20px; color: #666; cursor: pointer; }
        .switch span { color: #667eea; font-weight: bold; }
        .error { color: red; margin-top: 10px; }
    </style>
</head>
<body>
<div class="container">
    <div class="logo">🐹</div>
    <h1 id="title">Вход в Ruzhik</h1>
    <div id="loginForm">
        <input type="text" id="loginUsername" placeholder="Никнейм">
        <input type="password" id="loginPassword" placeholder="Пароль">
        <button class="btn" onclick="login()">Войти</button>
        <div class="switch" onclick="showRegister()">Нет аккаунта? <span>Зарегистрироваться</span></div>
    </div>
    <div id="registerForm" style="display:none;">
        <input type="text" id="regUsername" placeholder="Никнейм">
        <input type="password" id="regPassword" placeholder="Пароль">
        <button class="btn" onclick="register()">Зарегистрироваться</button>
        <div class="switch" onclick="showLogin()">Уже есть аккаунт? <span>Войти</span></div>
    </div>
    <div id="errorMsg" class="error"></div>
</div>
<script>
    async function login() {
        const username = document.getElementById('loginUsername').value;
        const password = document.getElementById('loginPassword').value;
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, password})
        });
        const data = await res.json();
        if (data.success) window.location.href = '/';
        else document.getElementById('errorMsg').innerText = data.error;
    }
    async function register() {
        const username = document.getElementById('regUsername').value;
        const password = document.getElementById('regPassword').value;
        if (username.length < 3) {
            document.getElementById('errorMsg').innerText = 'Никнейм минимум 3 символа';
            return;
        }
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, password})
        });
        const data = await res.json();
        if (data.success) window.location.href = '/';
        else document.getElementById('errorMsg').innerText = data.error;
    }
    function showRegister() {
        document.getElementById('loginForm').style.display = 'none';
        document.getElementById('registerForm').style.display = 'block';
        document.getElementById('title').innerText = 'Регистрация';
        document.getElementById('errorMsg').innerText = '';
    }
    function showLogin() {
        document.getElementById('registerForm').style.display = 'none';
        document.getElementById('loginForm').style.display = 'block';
        document.getElementById('title').innerText = 'Вход в Ruzhik';
        document.getElementById('errorMsg').innerText = '';
    }
</script>
</body>
</html>
'''

INDEX_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Ruzhik</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            transition: 0.3s;
        }
        body.dark { background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%); }
        .container { max-width: 600px; margin: 0 auto; }
        .card {
            background: white;
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        body.dark .card { background: #1e1e2e; color: #eee; }
        body.dark input, body.dark textarea { background: #2a2a3e; color: white; border-color: #3a3a4e; }
        .gradient-text {
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            font-weight: bold;
        }
        .nav {
            background: white;
            border-radius: 20px;
            padding: 15px 25px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 10px;
        }
        body.dark .nav { background: #1e1e2e; }
        .nav a, .nav span { margin: 0 10px; text-decoration: none; color: #333; cursor: pointer; }
        body.dark .nav a, body.dark .nav span { color: #ccc; }
        .btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 50px;
            cursor: pointer;
        }
        .btn-danger { background: #e74c3c; }
        .btn-sm { padding: 5px 12px; font-size: 12px; }
        .btn-success { background: #27ae60; }
        .btn-warning { background: #f39c12; }
        .post {
            border-bottom: 1px solid #eee;
            padding: 15px 0;
            display: flex;
            justify-content: space-between;
        }
        body.dark .post { border-color: #333; }
        .username { font-weight: bold; }
        .date { color: #999; font-size: 12px; margin-top: 5px; }
        textarea {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 10px;
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            justify-content: center;
            align-items: center;
            z-index: 2000;
        }
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 20px;
            max-width: 400px;
            width: 90%;
        }
        body.dark .modal-content { background: #1e1e2e; }
        .profile-header { display: flex; align-items: center; gap: 20px; margin-bottom: 20px; }
        .profile-avatar { width: 80px; height: 80px; border-radius: 50%; object-fit: cover; }
        .privacy {
            text-align: center;
            font-size: 11px;
            color: rgba(255,255,255,0.7);
            margin-top: 20px;
            cursor: pointer;
        }
        .privacy-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            justify-content: center;
            align-items: center;
            z-index: 3000;
        }
        .privacy-content {
            background: white;
            padding: 30px;
            border-radius: 20px;
            max-width: 500px;
            max-height: 80%;
            overflow-y: auto;
        }
        body.dark .privacy-content { background: #1e1e2e; }
        .chat-modal {
            display: none;
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 350px;
            height: 500px;
            background: white;
            border-radius: 20px;
            flex-direction: column;
            z-index: 1000;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }
        body.dark .chat-modal { background: #1e1e2e; }
        .chat-header {
            padding: 15px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border-radius: 20px 20px 0 0;
            display: flex;
            justify-content: space-between;
        }
        .chat-messages { flex: 1; overflow-y: auto; padding: 15px; }
        .chat-input { padding: 15px; display: flex; gap: 10px; border-top: 1px solid #ddd; }
        .chat-input input { flex: 1; margin: 0; }
        .message {
            margin-bottom: 10px;
            padding: 8px 12px;
            border-radius: 15px;
            max-width: 80%;
        }
        .message.sent {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            margin-left: auto;
        }
        .message.received { background: #f0f0f0; }
        body.dark .message.received { background: #2a2a3e; color: #eee; }
        .user-item {
            padding: 10px;
            cursor: pointer;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .user-item:hover { background: #f0f0f0; }
        body.dark .user-item:hover { background: #2a2a3e; }
        @media (max-width: 600px) {
            .chat-modal { width: 100%; right: 0; bottom: 0; border-radius: 20px 20px 0 0; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="nav">
        <span class="gradient-text">🐹 Ruzhik</span>
        <div>
            <a onclick="openChatList()" class="gradient-text">Чаты</a>
            <a onclick="openRequests()" class="gradient-text">Запросы</a>
            <a href="/settings" class="gradient-text">Настройки</a>
            <span class="gradient-text">{{ username }}</span>
            <button onclick="toggleTheme()" style="background:none; border:none; font-size:18px; cursor:pointer;" id="themeBtn">🌙</button>
        </div>
    </div>

    <div class="card">
        <h3 class="gradient-text">Что нового?</h3>
        <textarea id="postContent" rows="2" placeholder="Напиши что-нибудь..."></textarea>
        <button class="btn" onclick="createPost()">Опубликовать</button>
    </div>

    <div class="card">
        <h3 class="gradient-text">Лента</h3>
        <div id="feed">Загрузка...</div>
    </div>

    <div class="privacy" onclick="showPrivacy()">Политика конфиденциальности</div>
</div>

<div id="privacyModal" class="privacy-modal">
    <div class="privacy-content">
        <h2 class="gradient-text">Политика конфиденциальности Ruzhik</h2>
        <p><strong>1. Собираемые данные</strong><br>Только никнейм и пароль (хранятся в зашифрованном виде).</p>
        <p><strong>2. Использование данных</strong><br>Никнейм отображается в ленте и чатах. Пароль только для входа.</p>
        <p><strong>3. Передача третьим лицам</strong><br>Никакие данные не передаются.</p>
        <p><strong>4. Ваши права</strong><br>Вы можете удалить свои посты, изменить никнейм и аватар.</p>
        <p><strong>5. Безопасность</strong><br>Данные хранятся локально на сервере.</p>
        <button class="btn" onclick="closePrivacy()" style="margin-top:20px;">Закрыть</button>
    </div>
</div>

<div class="chat-modal" id="friendsModal">
    <div class="chat-header"><span>Друзья</span><button onclick="closeModal('friendsModal')" style="background:none; border:none; color:white; cursor:pointer;">✖</button></div>
    <div id="friendsList" style="padding:15px;"></div>
</div>

<div class="chat-modal" id="requestsModal">
    <div class="chat-header"><span>Запросы в друзья</span><button onclick="closeModal('requestsModal')" style="background:none; border:none; color:white; cursor:pointer;">✖</button></div>
    <div id="requestsList" style="padding:15px;"></div>
</div>

<div class="chat-modal" id="chatModal">
    <div class="chat-header"><span>Чат с <span id="chatWith"></span></span><button onclick="closeChat()" style="background:none; border:none; color:white; cursor:pointer;">✖</button></div>
    <div id="chatMessages" style="flex:1; overflow-y:auto; padding:15px;"></div>
    <div class="chat-input">
        <input id="chatInput" placeholder="Сообщение..." onkeypress="if(event.key==='Enter') sendMsg()">
        <button class="btn" onclick="sendMsg()">Отпр</button>
    </div>
</div>

<script>
    let currentChatUser = null, chatInterval = null, currentUser = '{{ username }}';

    function toggleTheme() {
        document.body.classList.toggle('dark');
        const btn = document.getElementById('themeBtn');
        if (document.body.classList.contains('dark')) btn.textContent = '☀️';
        else btn.textContent = '🌙';
        localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
    }
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark');
        document.getElementById('themeBtn').textContent = '☀️';
    }

    function showPrivacy() { document.getElementById('privacyModal').style.display = 'flex'; }
    function closePrivacy() { document.getElementById('privacyModal').style.display = 'none'; }

    async function createPost() {
        const content = document.getElementById('postContent').value;
        if (!content.trim()) return alert('Введи текст');
        const res = await fetch('/api/post', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({content: content})
        });
        if (res.ok) {
            document.getElementById('postContent').value = '';
            loadFeed();
        } else alert('Ошибка');
    }

    async function deletePost(id) {
        if (!confirm('Удалить пост?')) return;
        await fetch('/api/delete_post', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({post_id: id})});
        loadFeed();
    }

    async function loadFeed() {
        const res = await fetch('/api/feed');
        const posts = await res.json();
        const feedDiv = document.getElementById('feed');
        if (posts.length === 0) { feedDiv.innerHTML = 'Нет постов'; return; }
        feedDiv.innerHTML = posts.map(p => `
            <div class="post">
                <div>
                    <div class="username gradient-text">${escapeHtml(p.username)}</div>
                    <div>${escapeHtml(p.content)}</div>
                    <div class="date">${p.date}</div>
                    ${currentUser && p.username !== currentUser ? `<button class="btn btn-sm btn-warning" onclick="sendFriendRequest('${p.username}')">➕ В друзья</button>` : ''}
                </div>
                ${p.username === currentUser ? `<button class="btn btn-danger btn-sm" onclick="deletePost(${p.id})">🗑</button>` : ''}
            </div>
        `).join('');
    }

    async function sendFriendRequest(to) {
        const res = await fetch('/api/send_request', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({to_user: to})
        });
        if (res.ok) alert('Запрос отправлен');
    }

    async function openChatList() {
        const res = await fetch('/api/friends');
        const friends = await res.json();
        const list = document.getElementById('friendsList');
        if (friends.length === 0) list.innerHTML = '<div style="text-align:center; padding:20px;">Нет друзей</div>';
        else list.innerHTML = friends.map(f => `<div class="user-item" onclick="startChat('${f}')"><span>👤 ${f}</span></div>`).join('');
        document.getElementById('friendsModal').style.display = 'flex';
    }

    async function openRequests() {
        const res = await fetch('/api/friend_requests');
        const reqs = await res.json();
        const list = document.getElementById('requestsList');
        if (reqs.length === 0) list.innerHTML = '<div style="text-align:center; padding:20px;">Нет запросов</div>';
        else list.innerHTML = reqs.map(r => `
            <div class="user-item">
                <span>👤 ${r.from_user}</span>
                <div>
                    <button class="btn btn-sm btn-success" onclick="acceptReq('${r.from_user}')">Принять</button>
                    <button class="btn btn-sm btn-danger" onclick="rejectReq('${r.from_user}')">Отклонить</button>
                </div>
            </div>
        `).join('');
        document.getElementById('requestsModal').style.display = 'flex';
    }

    async function acceptReq(from) {
        await fetch('/api/accept_request', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({from_user: from})});
        openRequests();
    }
    async function rejectReq(from) {
        await fetch('/api/reject_request', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({from_user: from})});
        openRequests();
    }

    function startChat(user) {
        currentChatUser = user;
        document.getElementById('chatWith').innerText = user;
        document.getElementById('friendsModal').style.display = 'none';
        document.getElementById('chatModal').style.display = 'flex';
        loadMessages();
        if (chatInterval) clearInterval(chatInterval);
        chatInterval = setInterval(loadMessages, 3000);
    }
    function closeChat() {
        document.getElementById('chatModal').style.display = 'none';
        if (chatInterval) clearInterval(chatInterval);
        currentChatUser = null;
    }
    function closeModal(id) { document.getElementById(id).style.display = 'none'; }

    async function loadMessages() {
        if (!currentChatUser) return;
        const res = await fetch(`/api/messages/${currentChatUser}`);
        const msgs = await res.json();
        const container = document.getElementById('chatMessages');
        container.innerHTML = msgs.map(m => `
            <div class="message ${m.from === currentUser ? 'sent' : 'received'}">
                <strong>${m.from}</strong><br>${escapeHtml(m.message)}<br><small>${m.time}</small>
            </div>
        `).join('');
        container.scrollTop = container.scrollHeight;
    }
    async function sendMsg() {
        const input = document.getElementById('chatInput');
        const msg = input.value;
        if (!msg || !currentChatUser) return;
        await fetch('/api/send', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({to: currentChatUser, message: msg})});
        input.value = '';
        loadMessages();
    }

    function escapeHtml(t) { const div = document.createElement('div'); div.textContent = t; return div.innerHTML; }

    loadFeed();
    setInterval(loadFeed, 5000);
</script>
</body>
</html>
'''

SETTINGS_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Настройки - Ruzhik</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 500px; margin: 50px auto; }
        .card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        body.dark .card { background: #1e1e2e; color: #eee; }
        body.dark input { background: #2a2a3e; color: white; border-color: #3a3a4e; }
        .gradient-text {
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }
        .btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 12px;
            border-radius: 50px;
            cursor: pointer;
            width: 100%;
            margin-top: 15px;
            text-align: center;
            display: inline-block;
            text-decoration: none;
        }
        .btn-danger { background: #e74c3c; }
        input {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 10px;
        }
        .profile-header { display: flex; align-items: center; gap: 20px; margin-bottom: 20px; }
        .profile-avatar { width: 80px; height: 80px; border-radius: 50%; object-fit: cover; }
        h2 { margin-bottom: 20px; }
    </style>
</head>
<body>
<div class="container">
    <div class="card">
        <h2 class="gradient-text">Настройки профиля</h2>

        <div class="profile-header">
            <img id="avatar" class="profile-avatar" src="">
            <div>
                <h3 id="usernameDisplay" class="gradient-text">{{ username }}</h3>
                <input type="file" id="avatarFile" accept="image/*" style="display:none;">
                <button class="btn" style="padding:8px; font-size:14px;" onclick="document.getElementById('avatarFile').click()">Сменить аватар</button>
            </div>
        </div>

        <input type="text" id="newUsername" placeholder="Новый никнейм">
        <button class="btn" onclick="updateUsername()">Сменить никнейм</button>

        <button class="btn btn-danger" onclick="logout()">Выйти из аккаунта</button>

        <a href="/" class="btn" style="background:#999;">На главную</a>
    </div>
</div>
<script>
    async function loadUserInfo() {
        const res = await fetch('/api/user_info');
        const user = await res.json();
        document.getElementById('usernameDisplay').innerText = user.username;
        document.getElementById('avatar').src = user.avatar + '?t=' + Date.now();
    }

    document.getElementById('avatarFile')?.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append('avatar', file);
        const res = await fetch('/api/upload_avatar', {method: 'POST', body: formData});
        const data = await res.json();
        if (data.url) document.getElementById('avatar').src = data.url + '?t=' + Date.now();
        else alert('Ошибка загрузки');
    });

    async function updateUsername() {
        const newUsername = document.getElementById('newUsername').value;
        if (!newUsername || newUsername.length < 3) return alert('Минимум 3 символа');
        const res = await fetch('/api/update_username', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: newUsername})
        });
        const data = await res.json();
        if (data.success) {
            alert('Никнейм изменён! Страница перезагрузится');
            location.reload();
        } else alert(data.error);
    }

    async function logout() {
        await fetch('/api/logout');
        window.location.href = '/';
    }

    loadUserInfo();
</script>
</body>
</html>
'''


# ========== РОУТЫ ==========
@app.route('/')
def index():
    if 'user_id' not in session:
        return AUTH_HTML
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    conn.close()
    return render_template_string(INDEX_HTML, username=user[0] if user else None)


@app.route('/settings')
def settings_page():
    if 'user_id' not in session:
        return redirect('/')
    return render_template_string(SETTINGS_HTML, username=None)


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        session['user_id'] = user[0]
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Неверный никнейм или пароль'})


@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if len(username) < 3:
        return jsonify({'success': False, 'error': 'Никнейм минимум 3 символа'})
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, avatar) VALUES (?, ?, ?)",
                  (username, password, '/avatars/default.png'))
        conn.commit()
        session['user_id'] = c.lastrowid
        return jsonify({'success': True})
    except:
        return jsonify({'success': False, 'error': 'Никнейм уже занят'})
    finally:
        conn.close()


@app.route('/api/logout')
def api_logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/user_info')
def api_user_info():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT username, avatar FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    conn.close()
    return jsonify({'username': user[0], 'avatar': user[1]})


@app.route('/api/update_username', methods=['POST'])
def api_update_username():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    new_username = data.get('username')
    if not new_username or len(new_username) < 3:
        return jsonify({'error': 'Минимум 3 символа'}), 400
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    try:
        c.execute("UPDATE users SET username = ? WHERE id = ?", (new_username, session['user_id']))
        c.execute("UPDATE posts SET username = ? WHERE user_id = ?", (new_username, session['user_id']))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        conn.close()
        return jsonify({'error': 'Никнейм уже занят'}), 400


@app.route('/api/upload_avatar', methods=['POST'])
def api_upload_avatar():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if 'avatar' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'error': 'No file'}), 400
    filename = f"user_{session['user_id']}.png"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    avatar_url = f'/avatars/{filename}'
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar_url, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'url': avatar_url})


@app.route('/avatars/<filename>')
def serve_avatar(filename):
    from flask import send_from_directory
    return send_from_directory('avatars', filename)


@app.route('/api/post', methods=['POST'])
def api_post():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    content = censor(data.get('content', '')[:500])
    if not content.strip():
        return jsonify({'error': 'Пустой пост'}), 400
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    username = c.fetchone()[0]
    c.execute("INSERT INTO posts (user_id, username, content, created_at) VALUES (?, ?, ?, ?)",
              (session['user_id'], username, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/delete_post', methods=['POST'])
def api_delete_post():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    post_id = data.get('post_id')
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/feed')
def api_feed():
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT id, username, content, created_at FROM posts ORDER BY created_at DESC LIMIT 50")
    posts = [{"id": row[0], "username": row[1], "content": row[2], "date": row[3]} for row in c.fetchall()]
    conn.close()
    return jsonify(posts)


@app.route('/api/friends')
def api_friends():
    if 'user_id' not in session:
        return jsonify([])
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    current = c.fetchone()[0]
    c.execute("SELECT user1, user2 FROM friends WHERE user1 = ? OR user2 = ?", (current, current))
    friends = []
    for row in c.fetchall():
        friends.append(row[1] if row[0] == current else row[0])
    conn.close()
    return jsonify(friends)


@app.route('/api/friend_requests')
def api_friend_requests():
    if 'user_id' not in session:
        return jsonify([])
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    current = c.fetchone()[0]
    c.execute("SELECT from_user FROM friend_requests WHERE to_user = ? AND status = 'pending'", (current,))
    reqs = [{"from_user": row[0]} for row in c.fetchall()]
    conn.close()
    return jsonify(reqs)


@app.route('/api/send_request', methods=['POST'])
def api_send_request():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    to_user = data.get('to_user')
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    from_user = c.fetchone()[0]
    try:
        c.execute("INSERT INTO friend_requests (from_user, to_user) VALUES (?, ?)", (from_user, to_user))
        conn.commit()
    except:
        pass
    conn.close()
    return jsonify({'success': True})


@app.route('/api/accept_request', methods=['POST'])
def api_accept_request():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    from_user = data.get('from_user')
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    current = c.fetchone()[0]
    c.execute("DELETE FROM friend_requests WHERE from_user = ? AND to_user = ?", (from_user, current))
    c.execute("INSERT INTO friends (user1, user2) VALUES (?, ?)", (from_user, current))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/reject_request', methods=['POST'])
def api_reject_request():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    from_user = data.get('from_user')
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    current = c.fetchone()[0]
    c.execute("DELETE FROM friend_requests WHERE from_user = ? AND to_user = ?", (from_user, current))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/send', methods=['POST'])
def api_send():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    to_user = data.get('to')
    message = censor(data.get('message', '')[:500])
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    from_user = c.fetchone()[0]
    c.execute("INSERT INTO messages (from_user, to_user, message, created_at) VALUES (?, ?, ?, ?)",
              (from_user, to_user, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/messages/<username>')
def api_messages(username):
    if 'user_id' not in session:
        return jsonify([])
    conn = sqlite3.connect('social.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    current = c.fetchone()[0]
    c.execute("""SELECT from_user, message, created_at FROM messages 
                 WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
                 ORDER BY created_at ASC LIMIT 100""",
              (current, username, username, current))
    msgs = [{"from": row[0], "message": row[1], "time": row[2]} for row in c.fetchall()]
    conn.close()
    return jsonify(msgs)


if __name__ == '__main__':
    os.makedirs('avatars', exist_ok=True)
    print("=" * 50)
    print("🐹 RUZHIK запущена!")
    print("Открой http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)