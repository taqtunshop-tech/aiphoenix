import http.server, socketserver, os, sys, json

os.chdir(r'C:\Users\ROM\Downloads\ИИ теплообмен')

PORT = 8080

handler = http.server.SimpleHTTPRequestHandler
handler.extensions_map.update({
    '.json': 'application/json',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.html': 'text/html',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.mp4': 'video/mp4',
})

with socketserver.TCPServer(("", PORT), handler) as httpd:
    print(f"Server running at http://localhost:{PORT}")
    print(f"Serving: {os.getcwd()}")
    print("Press Ctrl+C to stop")
    httpd.serve_forever()
