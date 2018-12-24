import socket, os, select, re, json

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
                body = msg['envelope']['dataMessage']['message']
                command = ':' + number + ' PRIVMSG ' + number + ' :' + body
                print('< ' + command)
                conn.sendall((command + '\r\n').encode('utf-8'))
                attachments = msg['envelope']['dataMessage']['attachments']
                if len(attachments) > 0:
                    for j in range(len(attachments)):
                        body = 'File attached: ' + msg['envelope']['dataMessage']['attachments'][j]
                        command = ':' + number + ' PRIVMSG ' + number + ' :' + body
                        print('< ' + command)
                        conn.sendall((command + '\r\n').encode('utf-8'))
            
client_connection, client_address = listen_socket.accept()

while True:
    ready = select.select([client_connection], [], [], 5)
    if (not ready[0]):
        if _authorized:
            get_messages(client_connection)
        continue

    request = client_connection.recv(1024)
    req_s = request.decode('utf-8').split("\r\n")

    if len(req_s) == 1 and req_s[0] == '':
        _nick = ''
        _pass = ''
        _authorized = False
        client_connection.close()
        client_connection, client_address = listen_socket.accept()

    for i in range(len(req_s)):
        print('> ' + req_s[i])
        if req_s[i][0:4] == 'NICK':
            _nick = req_s[i][5:]
        if req_s[i][0:4] == 'PASS':
            _pass = req_s[i][5:]
        if req_s[i][0:7] == 'PRIVMSG' and _authorized:
            pos = req_s[i].find(':')
            privmsg(req_s[i][8:pos], req_s[i][pos+1:])

    if _nick == NICK and _pass == PASS and not _authorized:
        client_connection.sendall('375 signal-irc :- Welcome to Signal IRC bridge\r\n'.encode('utf-8'))
        _authorized = True

client_connection.close()