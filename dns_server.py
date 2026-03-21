import socket
import struct
from dnslib import DNSRecord, RR, A, AAAA
from dnslib.server import BaseResolver, ThreadingUDPServer
from typing import Tuple
import logging
from dns_filter import DNSFilter, FilterAction

logger = logging.getLogger("DNSResolver")

class CustomDNSResolver(BaseResolver):
    """Custom DNS resolver that uses our filter"""

    def __init__(self, dns_filter: DNSFilter, upstream_dns: str = "8.8.8.8", upstream_port: int = 53):
        self.dns_filter = dns_filter
        self.upstream_dns = upstream_dns
        self.upstream_port = upstream_port
        self.blocked_ip = "127.0.0.1"  # Return localhost for blocked domains
        super().__init__()

    def resolve(self, request, handler):
        """
        Resolve DNS query using our custom filter

        Args:
            request: DNS request
            handler: Handler with client info
        """
        # Extract query information
        query_name = request.questions[0].qname
        query_qtype = request.questions[0].qtype

        # Get device ID from handler (can be extended for more sophisticated tracking)
        device_id = handler.client_address[0] if handler else "unknown"

        logger.info(f"DNS Query from {device_id}: {query_name} (type: {query_qtype})")

        # Apply filter
        filter_result = self.dns_filter.filter_query(str(query_name).rstrip('.'), device_id)
        logger.info(f"Filter result: {filter_result}")

        # Build response
        reply = request.reply()

        if filter_result.action == FilterAction.BLOCK:
            # Return blocked response (NXDOMAIN or localhost)
            logger.warning(f"BLOCKED: {query_name} - {filter_result.reason}")
            reply.header.rcode = 3  # NXDOMAIN
            return reply

        elif filter_result.action == FilterAction.ALLOW:
            # Forward to upstream DNS
            logger.info(f"ALLOWED: {query_name} - {filter_result.reason}")
            return self._query_upstream(request, query_name, query_qtype)

        else:  # REQUIRE_APPROVAL
            # Return REFUSED response
            logger.info(f"APPROVAL REQUIRED: {query_name} - {filter_result.reason}")
            reply.header.rcode = 5  # REFUSED
            return reply

    def _query_upstream(self, request, query_name, query_qtype):
        """Query upstream DNS server"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            sock.sendto(request.pack(), (self.upstream_dns, self.upstream_port))

            response_data, _ = sock.recvfrom(4096)
            sock.close()

            return DNSRecord.parse(response_data)

        except Exception as e:
            logger.error(f"Error querying upstream DNS: {e}")
            reply = request.reply()
            reply.header.rcode = 2  # SERVFAIL
            return reply

class DNSServer:
    """DNS server wrapper for easy setup and management"""

    def __init__(self, dns_filter: DNSFilter, listen_port: int = 5053, upstream_dns: str = "8.8.8.8"):
        """
        Initialize DNS server

        Args:
            dns_filter: DNSFilter instance to use
            listen_port: Port to listen on
            upstream_dns: Upstream DNS server to forward queries to
        """
        self.dns_filter = dns_filter
        self.listen_port = listen_port
        self.upstream_dns = upstream_dns
        self.server = None
        self.resolver = CustomDNSResolver(dns_filter, upstream_dns)

    def start(self, listen_address: str = "0.0.0.0"):
        """Start the DNS server"""
        logger.info(f"Starting DNS server on {listen_address}:{self.listen_port}")

        # Configure logging
        logging.basicConfig(level=logging.INFO)

        try:
            self.server = ThreadingUDPServer(
                (listen_address, self.listen_port),
                self.resolver
            )
            logger.info(f"DNS server started successfully on {listen_address}:{self.listen_port}")
            self.server.start()
        except PermissionError:
            logger.error(f"Permission denied. DNS servers typically require root access.")
            raise
        except Exception as e:
            logger.error(f"Failed to start DNS server: {e}")
            raise

    def stop(self):
        """Stop the DNS server"""
        if self.server:
            logger.info("Stopping DNS server...")
            self.server.stop()
            self.server = None

    def get_status(self) -> dict:
        """Get server status"""
        return {
            "listening_port": self.listen_port,
            "upstream_dns": self.upstream_dns,
            "is_running": self.server is not None,
            "filter_stats": self.dns_filter.get_stats(),
        }
