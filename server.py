import socket, os, select, re, json, time

HOST, PORT = '', 9094
NICK, PASS = os.environ['SIGNAL_IRC_NICK'], os.environ['SIGNAL_IRC_PASS']
PATH = os.environ['SIGNAL_IRC_PATH'] if 'SIGNAL_IRC_PATH' in os.environ else '/run/user/1000/signal'

listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listen_socket.bind((HOST, PORT))
listen_socket.listen(1)

print('Starting signal-irc bridge on port ' + str(PORT) + ' ...')

_nick = ''
_pass = ''
_authorized = False

f = open(os.path.expanduser("~") + '/.signal-irc/addressbook')
users = json.loads(f.read())
f.close()

def privmsg(to, msg):
    number = to
    if to in users:
        number = users[to]
    cmd = "signal-cli --dbus send +" + number + " -m \"" + msg.replace('"', '\\"') + "\""
    os.system(cmd)

def get_messages(conn):
    f = open(PATH)
    data = f.read().replace(chr(0), '').split('\n')
    f.close()
    os.system('echo "" > ' + PATH)
    number = ''
    for i in range(len(data)):
        if len(data[i]) > 0:
            msg = json.loads(data[i])
            if msg['envelope']['dataMessage'] is not None:
                number = msg['envelope']['source'][1:]
                username = number
                for user in users:
                    if users[user] == number:
                        username = user
                        break

                body = msg['envelope']['dataMessage']['message'].split('\n')
                for l in range(len(body)):
                    command = ':' + username + ' PRIVMSG ' + username + ' :' + body[l]
                    conn.sendall((command + '\n').encode('utf-8'))
                attachments = msg['envelope']['dataMessage']['attachments']
                if len(attachments) > 0:
                    for a in range(len(attachments)):
                        body = 'file://' + os.path.expanduser('~/.local/share/signal-cli/attachments/' + str(msg['envelope']['dataMessage']['attachments'][a]['id']))
                        command = ':' + username + ' PRIVMSG ' + username + ' :' + body
                        conn.sendall((command + '\n').encode('utf-8'))
            
client_connection, client_address = listen_socket.accept()

last_ping = time.time()

while True:
    ready = select.select([client_connection], [], [], 5)
    if (not ready[0]):
        if _authorized:
            get_messages(client_connection)
            if time.time() - last_ping > 300:
                last_ping = time.time()
                client_connection.sendall(('PING ' + str(time.time()) + '\n').encode('utf-8'))

        continue

    request = client_connection.recv(1024)
    req_s = request.decode('utf-8').split("\n")

    if len(req_s) == 1 and req_s[0] == '':
        _nick = ''
        _pass = ''
        _authorized = False
        client_connection.close()
        client_connection, client_address = listen_socket.accept()

    for i in range(len(req_s)):
        if len(req_s[i]) > 0:
            print('> ' + req_s[i])
            req_s[i] = req_s[i].replace('\r', '')
        if req_s[i][0:4] == 'NICK':
            _nick = req_s[i][5:]
        if req_s[i][0:4] == 'PASS':
            _pass = req_s[i][5:]
        if req_s[i][0:7] == 'PRIVMSG' and _authorized:
            pos = req_s[i].find(':')
            privmsg(req_s[i][8:pos].strip(), req_s[i][pos+1:])
        if req_s[i][0:4] == 'JOIN' and _authorized:
            channel = req_s[i][5:]
            client_connection.sendall(('352 signal.asafonov.org ' + channel + ' ' + NICK + ' signal-irc signal-irc ' + NICK + ' H :0 ' + NICK + '\n').encode('utf-8'))
            for user in users:
                client_connection.sendall(('352 signal.asafonov.org ' + channel + ' ' + user + ' signal-irc signal-irc ' + user + ' H :0 ' + user + '\n').encode('utf-8'))
            client_connection.sendall(('315 ' + NICK + ' :End of WHO list\n').encode('utf-8'))

    if _nick == NICK and _pass == PASS and not _authorized:
        client_connection.sendall(('375 ' + NICK + ' :- Welcome to Signal IRC bridge\n').encode('utf-8'))
        _authorized = True

client_connection.close()
