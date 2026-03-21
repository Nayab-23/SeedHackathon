import socket


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
            return response
        except socket.timeout:
            return None
        except socket.error:
            return None
