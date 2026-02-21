"""Command server for Raspberry Pi 5 to control Pico display modes."""
import argparse
import json
import socket
import threading
import sys
import time


class DisplayCommandServer:
    def __init__(self, bind="0.0.0.0", port=5000):
        self.bind = bind
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.bind, self.port))
        self.server.listen(2)
        self.clients = set()
        self.clients_lock = threading.Lock()
        self.running = threading.Event()
        self.running.set()

    def start(self):
        threading.Thread(target=self._accept_loop, daemon=True).start()
        print(f"Listening for Pico connections on {self.bind}:{self.port}")

    def stop(self):
        self.running.clear()
        self.server.close()
        with self.clients_lock:
            for conn in list(self.clients):
                conn.close()
            self.clients.clear()

    def _accept_loop(self):
        while self.running.is_set():
            try:
                conn, addr = self.server.accept()
            except OSError:
                break
            print(f"Pico connected from {addr}")
            with self.clients_lock:
                self.clients.add(conn)
            threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()

    def _handle_client(self, conn, addr):
        buffer = b""
        try:
            while self.running.is_set():
                chunk = conn.recv(1024)
                if not chunk:
                    break
                buffer += chunk.replace(b"\r", b"")
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if line:
                        print(f"[pico {addr}] {line.decode('utf-8', 'replace')}")
        finally:
            with self.clients_lock:
                self.clients.discard(conn)
            conn.close()
            print(f"Pico disconnected {addr}")

    def broadcast(self, payload):
        if not payload:
            return
        frame = (json.dumps(payload) + "\n").encode()
        bad = []
        with self.clients_lock:
            for conn in list(self.clients):
                try:
                    conn.sendall(frame)
                except OSError:
                    bad.append(conn)
            for conn in bad:
                self.clients.discard(conn)
        return len(self.clients) > 0

    def send_mode(self, mode, payload=None):
        return self.broadcast({"cmd": "set_mode", "mode": mode, "payload": payload or {}})

    def send_refresh(self):
        return self.broadcast({"cmd": "refresh"})


def interactive_loop(server):
    print("Enter `mode <mode> <payload-json>`, `refresh`, or raw JSON commands. Type 'exit' to stop.")
    while True:
        try:
            line = input("command> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.lower() in {"exit", "quit"}:
            break
        if line.startswith("mode "):
            tokens = line.split(None, 2)
            mode = tokens[1]
            payload = {}
            if len(tokens) == 3:
                try:
                    payload = json.loads(tokens[2])
                except ValueError:
                    print("Invalid JSON payload.")
                    continue
            server.send_mode(mode, payload)
            continue
        if line.lower() == "refresh":
            server.send_refresh()
            continue
        try:
            candidate = json.loads(line)
        except ValueError:
            print("Unrecognized command. Use `mode`, `refresh`, or provide JSON.")
            continue
        server.broadcast(candidate)


def parse_args():
    parser = argparse.ArgumentParser(description="TCP command server for Pico display control")
    parser.add_argument("--bind", default="0.0.0.0", help="Host interface for the TCP server")
    parser.add_argument("--port", type=int, default=5000, help="TCP port the Pico clients connect to")
    parser.add_argument("--preload", help="Path to a JSON file with one command per line to send immediately after the first client connects")
    parser.add_argument("--headless", action="store_true", help="Send preload commands (if provided) and exit without interactive prompt")
    return parser.parse_args()


def main():
    args = parse_args()
    server = DisplayCommandServer(bind=args.bind, port=args.port)
    server.start()
    try:
        if args.preload:
            wait_for_connection(server)
            send_preload(args.preload, server)
        if not args.headless:
            interactive_loop(server)
    finally:
        server.stop()


def wait_for_connection(server, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        with server.clients_lock:
            if server.clients:
                return True
        time.sleep(0.25)
    print("Warning: no Pico client connected yet.")
    return False


def send_preload(path, server):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    payload = json.loads(line)
                except ValueError:
                    print(f"Skipping invalid JSON line: {line}")
                    continue
                server.broadcast(payload)
    except OSError as exc:
        print(f"Unable to read preload file: {exc}")


if __name__ == "__main__":
    main()
