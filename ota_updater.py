import socket
import os
import machine

def start_update_server(port=8080):
    addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    print(f'Update server listening on port {port}')
    
    while True:
        try:
            client, addr = s.accept()
            print('Client connected from', addr)
            request = client.recv(1024).decode()
            
            if request.startswith('POST /update'):
                content_length = 0
                # Parse headers to get content length
                while True:
                    line = b''
                    while True:
                        c = client.recv(1)
                        if c == b'\n':
                            break
                        line += c
                    if line == b'\r':
                        break
                    if line.startswith(b'Content-Length:'):
                        content_length = int(line.split(b':')[1])
                
                # Receive file content
                content = client.recv(content_length)
                
                # Backup existing file
                try:
                    os.rename('main.py', 'main.py.bak')
                except:
                    pass
                
                # Write new content
                with open('main.py', 'w') as f:
                    f.write(content.decode())
                
                # Send response
                response = 'HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\nUpdate successful'
                client.send(response.encode())
                client.close()
                
                print('Update successful, rebooting...')
                machine.reset()  # Reboot to load new code
                
            else:
                # Send update form
                html = '''HTTP/1.0 200 OK
Content-Type: text/html

<html>
<body>
<h1>ESP32 OTA Update</h1>
<form method="POST" action="/update" enctype="multipart/form-data">
    <input type="file" name="file">
    <input type="submit" value="Update">
</form>
</body>
</html>
'''
                client.send(html.encode())
                client.close()
                
        except Exception as e:
            print('Update server error:', e)
            try:
                client.close()
            except:
                pass