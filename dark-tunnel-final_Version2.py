#!/usr/bin/env python3
"""
Dark Tunnel Clone - Full VPN via Bug Host
With auto-retry like the Android app
"""

import socket
import threading
import subprocess
import time
import os
import sys
import signal

# ============ CONFIGURATION ============
# SSH Account
SSH_HOST = "us1.sshws.net"
SSH_USER = "fastssh.com-sha023"
SSH_PASS = "popopo123"

# Bug Host (zero-rated by ISP)
BUG_HOST = "arcotw.icicibank.com"

# Ports
LOCAL_PORT = 8989
SOCKS_PORT = 1080

# Retry settings
MAX_RETRIES = 15
RETRY_DELAY = 3
# =======================================

ssh_process = None
tunnel_running = False

def get_ip(host):
    try:
        return socket. gethostbyname(host)
    except:
        return None

def handle_client(client, bug_ip):
    """Handle client connection through bug host"""
    remote = None
    try:
        remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote.settimeout(30)
        remote.connect((bug_ip, 80))
        
        # Send HTTP CONNECT-style request to tunnel through Cloudflare
        # The payload tells Cloudflare to route to SSH server
        payload = f"GET / HTTP/1.1\r\nHost: {SSH_HOST}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n"
        remote.sendall(payload.encode())
        
        # Read response
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = remote.recv(1024)
            if not chunk: 
                break
            response += chunk
        
        if b"101" not in response:
            print(f"[-] WebSocket upgrade failed")
            return False
        
        print("[+] WebSocket tunnel established via bug host!")
        
        # Forward remaining data after headers
        extra = response.split(b"\r\n\r\n", 1)
        if len(extra) > 1 and extra[1]:
            client.sendall(extra[1])
        
        remote.settimeout(None)
        client.settimeout(None)
        
        def fwd(s, d):
            try:
                while True: 
                    data = s.recv(65536)
                    if not data:
                        break
                    d.sendall(data)
            except:
                pass
        
        t1 = threading.Thread(target=fwd, args=(client, remote))
        t2 = threading.Thread(target=fwd, args=(remote, client))
        t1.daemon = True
        t2.daemon = True
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        return True
        
    except Exception as e:
        print(f"[-] Connection error: {e}")
        return False
    finally:
        try: 
            client.close()
        except:
            pass
        try:
            if remote: 
                remote.close()
        except:
            pass

def start_tunnel_server(bug_ip):
    """Start local tunnel server"""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", LOCAL_PORT))
    srv.listen(5)
    srv.settimeout(1)
    
    global tunnel_running
    tunnel_running = True
    
    while tunnel_running:
        try: 
            c, a = srv. accept()
            print(f"[+] Tunnel connection from {a}")
            threading.Thread(target=handle_client, args=(c, bug_ip), daemon=True).start()
        except socket.timeout:
            continue
        except: 
            break
    
    srv.close()

def start_ssh_socks():
    """Start SSH SOCKS proxy with retry"""
    global ssh_process
    
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n[*] SSH attempt {attempt}/{MAX_RETRIES}...")
        
        cmd = [
            "sshpass", "-p", SSH_PASS,
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", f"ProxyCommand=nc 127.0.0.1 {LOCAL_PORT}",
            "-N", "-D", f"127.0.0.1:{SOCKS_PORT}",
            f"{SSH_USER}@localhost"
        ]
        
        ssh_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait a bit and check if connected
        time.sleep(5)
        
        # Test SOCKS proxy
        try:
            test = subprocess.run(
                ["curl", "-s", "--max-time", "10", "-x", f"socks5h://127.0.0.1:{SOCKS_PORT}", "ifconfig.me"],
                capture_output=True,
                timeout=15
            )
            if test. returncode == 0 and test.stdout:
                ip = test.stdout.decode().strip()
                print(f"\n[+] SUCCESS!  Connected!")
                print(f"[+] Your VPN IP: {ip}")
                return True
        except: 
            pass
        
        # Kill failed attempt
        if ssh_process: 
            ssh_process.terminate()
            ssh_process.wait()
        
        if attempt < MAX_RETRIES: 
            print(f"[-] Failed.  Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
    
    return False

def cleanup(sig=None, frame=None):
    """Cleanup on exit"""
    global tunnel_running, ssh_process
    print("\n[*] Shutting down...")
    tunnel_running = False
    if ssh_process:
        ssh_process.terminate()
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    bug_ip = get_ip(BUG_HOST)
    ssh_ip = get_ip(SSH_HOST)
    
    if not bug_ip: 
        print(f"[-] Cannot resolve bug host:  {BUG_HOST}")
        sys.exit(1)
    
    print("=" * 55)
    print("   DARK TUNNEL - Linux Edition")
    print("=" * 55)
    print(f"  Bug Host: {BUG_HOST} ({bug_ip})")
    print(f"  SSH Server: {SSH_HOST} ({ssh_ip})")
    print(f"  SSH User: {SSH_USER}")
    print(f"  SOCKS Port: {SOCKS_PORT}")
    print("=" * 55)
    
    # Start tunnel server in background
    print("\n[*] Starting tunnel server...")
    tunnel_thread = threading.Thread(target=start_tunnel_server, args=(bug_ip,), daemon=True)
    tunnel_thread.start()
    time.sleep(1)
    
    # Start SSH with retry
    print("[*] Connecting SSH through bug host...")
    if start_ssh_socks():
        print("\n" + "=" * 55)
        print("  VPN CONNECTED!")
        print("=" * 55)
        print(f"  SOCKS Proxy: 127.0.0.1:{SOCKS_PORT}")
        print(f"  Route all traffic through bug host")
        print("  Press Ctrl+C to disconnect")
        print("=" * 55)
        
        # Keep running
        while True:
            time. sleep(10)
            # Check if SSH still running
            if ssh_process and ssh_process.poll() is not None:
                print("\n[-] SSH disconnected!  Reconnecting...")
                if not start_ssh_socks():
                    print("[-] Reconnection failed")
                    break
    else: 
        print("\n[-] Failed to connect after all retries")
        cleanup()

if __name__ == "__main__":
    main()