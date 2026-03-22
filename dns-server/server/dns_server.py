import socket
import threading
import time
from dnslib import DNSRecord, QTYPE
from openclaw.observer import OpenClaw, Action
from server.filter import DomainFilter
from server.resolver import Resolver
from server.blocker import Blocker


class DNSServer:
    def __init__(self, config: dict, openclaw: OpenClaw):
        self.config = config
        self.openclaw = openclaw
        self.listen_address = config["server"]["listen_address"]
        self.port = config["server"]["port"]

        self.filter = DomainFilter(
            config["lists"]["blacklist"], config["lists"]["whitelist"]
        )

        self.resolver = Resolver(
            config["upstream"]["dns_server"],
            config["upstream"]["port"],
            config["upstream"]["timeout"],
        )

        self.blocker = Blocker(config["blocking"]["mode"])

        self.socket = None
        self.running = False

    def _get_query_type_name(self, qtype):
        try:
            return QTYPE.get(qtype).name
        except:
            return str(qtype)

    def _build_servfail_response(self, query_data: bytes) -> bytes:
        try:
            request = DNSRecord.parse(query_data)
            reply = request.reply()
            reply.header.rcode = 2  # SERVFAIL
            return reply.pack()
        except:
            return b""

    def _handle_query(self, data: bytes, client_addr: tuple):
        start_time = time.time()
        client_ip = client_addr[0]

        print(f"[CONN] Client: {client_ip}:{client_addr[1]} connected")

        try:
            request = DNSRecord.parse(data)
            domain = str(request.q.qname)
            query_type = self._get_query_type_name(request.q.qtype)
            print(f"[RECV] {client_ip} -> {domain} ({query_type})")
        except Exception as e:
            response_ms = (time.time() - start_time) * 1000
            print(f"[ERR] Failed to parse from {client_ip}: {e}")
            self.openclaw.observe(
                client_ip=client_ip,
                domain="[PARSE_ERROR]",
                query_type="UNKNOWN",
                action=Action.ERROR,
                response_ms=response_ms,
                extra=str(e),
            )
            return

        action = self.filter.check(domain)

        if action == Action.BLOCKED:
            print(f"[BLOCK] {domain} blocked for {client_ip}")
            response_data = self.blocker.build_blocked_response(data)
        else:
            response_data = self.resolver.resolve(data)
            if response_data is None:
                print(f"[ERR] Upstream failed for {client_ip} - {domain}")
                response_data = self._build_servfail_response(data)
                action = Action.ERROR
            else:
                print(f"[OK] Forwarded {domain} for {client_ip}")

        response_ms = (time.time() - start_time) * 1000

        self.openclaw.observe(
            client_ip=client_ip,
            domain=domain,
            query_type=query_type,
            action=action,
            response_ms=response_ms,
        )

        try:
            self.socket.sendto(response_data, client_addr)
        except Exception as e:
            print(f"[ERR] Send failed to {client_ip}: {e}")

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(1.0)
        self.socket.bind((self.listen_address, self.port))

        self.running = True
        print(f"[*] DNS Server listening on {self.listen_address}:{self.port}")
        print(
            f"[*] Upstream DNS: {self.config['upstream']['dns_server']}:{self.config['upstream']['port']}"
        )
        print(f"[*] Blocking mode: {self.config['blocking']['mode']}")
        print("[*] Press Ctrl+C to stop\n")

        try:
            while self.running:
                try:
                    data, client_addr = self.socket.recvfrom(65535)
                    thread = threading.Thread(
                        target=self._handle_query, args=(data, client_addr), daemon=True
                    )
                    thread.start()
                except socket.timeout:
                    continue
                except Exception:
                    continue
        except KeyboardInterrupt:
            print("\n[!] Shutting down...")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
        self.openclaw.print_stats()
