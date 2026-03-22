import socket
from dnslib import DNSRecord

MAX_TTL = 5


class Resolver:
    def __init__(self, upstream_server: str, upstream_port: int, timeout: int = 3):
        self.upstream_server = upstream_server
        self.upstream_port = upstream_port
        self.timeout = timeout

    def resolve(self, query_data: bytes) -> bytes:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            sock.sendto(query_data, (self.upstream_server, self.upstream_port))
            response, _ = sock.recvfrom(65535)
            sock.close()
            return self._clamp_ttl(response)
        except socket.timeout:
            return None
        except socket.error:
            return None

    def _clamp_ttl(self, response: bytes) -> bytes:
        try:
            record = DNSRecord.parse(response)
            for rr in record.rr:
                if rr.ttl > MAX_TTL:
                    rr.ttl = MAX_TTL
            return record.pack()
        except Exception:
            return response
