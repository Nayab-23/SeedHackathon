import socket
import threading
import time
from dnslib import DNSRecord, QTYPE
from server.filter import DomainFilter, Action
from server.resolver import Resolver
from server.blocker import Blocker

try:
    from flttr.logger import log
except ImportError:
    log = None


class DNSServer:
    def __init__(self, config: dict, query_logger=None):
        self.config = config
        self.query_logger = query_logger
        self.listen_address = config["server"]["listen_address"]
        self.port = config["server"]["port"]

        self.domain_filter = DomainFilter(config["lists"]["blacklist"])

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
        except Exception:
            return str(qtype)

    def _build_servfail_response(self, query_data: bytes) -> bytes:
        try:
            request = DNSRecord.parse(query_data)
            reply = request.reply()
            reply.header.rcode = 2  # SERVFAIL
            return reply.pack()
        except Exception:
            return b""

    def _handle_query(self, data: bytes, client_addr: tuple):
        start_time = time.time()
        client_ip = client_addr[0]

        try:
            request = DNSRecord.parse(data)
            domain = str(request.q.qname)
            query_type = self._get_query_type_name(request.q.qtype)
        except Exception as e:
            if log:
                log.error(f"Failed to parse DNS packet from {client_ip}: {e}")
            return

        action = self.domain_filter.check(domain)

        if action == Action.BLOCKED:
            response_data = self.blocker.build_blocked_response(data)
        else:
            response_data = self.resolver.resolve(data)
            if response_data is None:
                if log:
                    log.error(f"Upstream DNS failed for {domain} from {client_ip}")
                response_data = self._build_servfail_response(data)

        response_ms = (time.time() - start_time) * 1000

        if log:
            log.dns(action.value, domain, query_type, client_ip, response_ms)

        if self.query_logger:
            self.query_logger.log(client_ip, domain, query_type, action.value, response_ms)

        try:
            self.socket.sendto(response_data, client_addr)
        except Exception as e:
            if log:
                log.error(f"Send failed to {client_ip}: {e}")

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(1.0)
        self.socket.bind((self.listen_address, self.port))

        self.running = True
        if log:
            log.system(f"DNS listening on {self.listen_address}:{self.port}")
            log.system(f"Upstream: {self.config['upstream']['dns_server']}:{self.config['upstream']['port']}")
            log.system(f"Block mode: {self.config['blocking']['mode']}")
            log.system(f"Blacklist: {len(self.domain_filter.blacklist)} domains loaded")
        else:
            print(f"[FLTTR] DNS Server listening on {self.listen_address}:{self.port}")

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
            if log:
                log.system("Shutting down...")
            else:
                print("\n[FLTTR] Shutting down...")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
