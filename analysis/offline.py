"""Optional network guard for notebook verification; permit local kernel communication only."""
import ipaddress
import socket


def block_external_network():
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def permitted(address):
        if not isinstance(address, tuple):
            return True  # Unix-domain sockets are local.
        host = address[0]
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def connect(sock, address):
        if not permitted(address):
            raise RuntimeError("External network disabled for reproducibility verification")
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if not permitted(address):
            raise RuntimeError("External network disabled for reproducibility verification")
        return original_connect_ex(sock, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
