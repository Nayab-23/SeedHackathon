from dnslib import DNSRecord, QTYPE, RCODE
from dnslib.dns import A, AAAA, RR


class Blocker:
    def __init__(self, mode: str = "zero_ip"):
        self.mode = mode

    def build_blocked_response(self, query_data: bytes) -> bytes:
        request = DNSRecord.parse(query_data)
        reply = request.reply()

        if self.mode == "nxdomain":
            reply.header.rcode = RCODE.NXDOMAIN
        else:  # zero_ip mode
            qtype = request.q.qtype
            if qtype == QTYPE.A:
                reply.add_answer(
                    RR(
                        rname=request.q.qname,
                        rtype=QTYPE.A,
                        rclass=1,
                        ttl=1,
                        rdata=A("0.0.0.0"),
                    )
                )
            elif qtype == QTYPE.AAAA:
                reply.add_answer(
                    RR(
                        rname=request.q.qname,
                        rtype=QTYPE.AAAA,
                        rclass=1,
                        ttl=1,
                        rdata=AAAA("::"),
                    )
                )
            else:
                reply.header.rcode = RCODE.NXDOMAIN

        return reply.pack()
