import socket, os, select, re, json, time

HOST, PORT = '', 9094
NICK, PASS = os.environ['SIGNAL_IRC_NICK'], os.environ['SIGNAL_IRC_PASS']

listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listen_socket.bind((HOST, PORT))
listen_socket.listen(1)

print('Starting signal-irc bridge on port ' + str(PORT) + ' ...')

_nick = ''
_pass = ''
_authorized = False

def privmsg(to, msg):
    cmd = "signal-cli --dbus send +" + to + " -m \"" + msg + "\""
    os.system(cmd)

def get_messages(conn):
    f = open('/run/user/1000/signal')
    data = f.read().replace(chr(0), '').split('\n')
    f.close()
    os.system('echo "" > /run/user/1000/signal')
    number = ''
    for i in range(len(data)):
        if len(data[i]) > 0:
            msg = json.loads(data[i])
            if msg['envelope']['dataMessage'] is not None:
                number = msg['envelope']['source'][1:]
                body = msg['envelope']['dataMessage']['message'].split('\n')
                for l in range(len(body)):
                    command = ':' + number + ' PRIVMSG ' + number + ' :' + body[l]
                    conn.sendall((command + '\n').encode('utf-8'))
                attachments = msg['envelope']['dataMessage']['attachments']
                if len(attachments) > 0:
                    for a in range(len(attachments)):
                        body = 'file://' + os.path.expanduser('~/.local/share/signal-cli/attachments/' + str(msg['envelope']['dataMessage']['attachments'][a]['id']))
                        command = ':' + number + ' PRIVMSG ' + number + ' :' + body
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
            privmsg(req_s[i][8:pos], req_s[i][pos+1:])

    if _nick == NICK and _pass == PASS and not _authorized:
        client_connection.sendall('375 signal-irc :- Welcome to Signal IRC bridge\n'.encode('utf-8'))
        _authorized = True

client_connection.close()
