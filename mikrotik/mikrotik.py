#!/usr/bin/env python3
# encoding: utf-8
from _socket import SHUT_WR

import logging
import socket
import struct
from hashlib import md5
import binascii


logger = logging.getLogger("MikrotikAPI")


class MikrotikAPIError(Exception):
    pass


class MikrotikAPIErrorCategory:

    MISSING = 0
    ARGUMENT_VALUE = 1
    INTERRUPTED = 2
    SCRIPT_FAILURE = 3
    GENERAL_FAILURE = 4
    API_FAILURE = 5
    TTY_FAILURE = 6
    RETURN_VALUE = 7


def pack_length(length):
    """
    Pack api request length.
    http://wiki.mikrotik.com/wiki/Manual:API#Protocol
    """
    if length < 0x80:
        return struct.pack("!B", length)
    elif length <= 0x3FFF:
        length = length | 0x8000
        return struct.pack("!BB", (length >> 8) & 0xFF, length & 0xFF)
    elif length <= 0x1FFFFF:
        length = length | 0xC00000
        return struct.pack("!BBB", length >> 16, (length & 0xFFFF) >> 8, length & 0xFF)
    elif length <= 0xFFFFFFF:
        length = length | 0xE0000000
        return struct.pack("!BBBB", length >> 24, (length & 0xFFFFFF) >> 16, (length & 0xFFFF) >> 8, length & 0xFF)
    else:
        raise MikrotikAPIError("Too long command!")


def unpack_length(length):
    """
    Unpack api request length.
    :param length: length string to unpack
    :return: length as integer
    """
    if len(length) == 1:
        return ord(length)
    elif len(length) == 2:
        c = ord(length[0]) & ~0xC0
        c <<= 8
        return c + ord(length[1])
    elif len(length) == 3:
        c = ord(length[0]) & ~0xE0
        c <<= 8
        c += ord(length[1])
        c <<= 8
        return c + ord(length[2])
    elif len(length) == 4 and (ord(length[0]) & 0xF0) == 0xE0:
        c = ord(length[0]) & ~0xF0
        c <<= 8
        c += ord(length[1])
        c <<= 8
        c += ord(length[2])
        c <<= 8
        return c + ord(length[3])
    elif len(length) == 4 and (ord(length[0]) & 0x8F) == 0xF0:
        c += ord(length[1])
        c <<= 8
        c += ord(length[2])
        c <<= 8
        c += ord(length[3])
        c <<= 8
        return c + ord(length[4])
    raise MikrotikAPIError("Invalid message length %s!" % length)

class MikrotikAPIResponseTypes:
    STATUS = 1
    ERROR = 2
    DATA = 3


class MikrotikApiResponse(object):
    def __init__(self, status, type, attributes=None, error=None):
        self.status = status
        self.type = type
        self.attributes = attributes
        self.error = error

    def __str__(self):
        return "!%s %s %s" % (self.status, ' '.join(["%s=%s" % (k, v) for k, v in self.attributes.items()]),
                              ' '.join(self.error))

class MikrotikAPIRequest(object):
    def __init__(self, command, attributes=None, api_attributes=None, queries=None):
        """
        Generate request for Mikrotik RouterOS API.
        """
        if not command.startswith('/'):
            raise MikrotikAPIError("Command should start with /")
        self.command = command
        if attributes:
            self.attributes = attributes
        else:
            self.attributes = {}
        if api_attributes:
            self.api_attributes = api_attributes
        else:
            self.api_attributes = {}
        if queries:
            self.queries = queries
        else:
            self.queries = {}

    def get_request(self):
        request = []


        request.append(pack_length(len(self.command)))
        request.append(self.command.encode("utf-8"))

        for attribute, value in self.attributes.items():
            attrib = "=%s=%s" % (attribute, value)
            request.append(pack_length(len(attrib)))
            request.append(attrib.encode("utf-8"))

        for attribute, value in self.api_attributes.items():
            attrib = ".%s=%s" % (attribute, value)
            request.append(pack_length(len(attrib)))
            request.append(attrib.encode("utf-8"))

        # TODO: complete query parsing
        for key, value in self.queries.items():
            if value:
                query = "?%s=%s" % (key, value)
            else:
                query = "?%s" % (key,)
            request.append(pack_length(len(query)))
            request.append(query.encode("utf-8"))

        request.append(pack_length(0))
        return b''.join(request)


class Mikrotik(object):
    def __init__(self, address, port=8728):
        self._address = address
        self._port = port
        self.connect()

    def connect(self):
        self._socket = socket.socket()
        self._socket.connect((self._address, self._port))

    def _send(self, data):
        logger.debug("Sending %s" % data)
        self._socket.send(data)

    def _recv(self):
        responses = b''
        while True:
            responses += self._socket.recv(2048)
            logger.debug("Got %s from API" % (responses,))
            if responses[-1] != 0:
                # Next iteration needed
                continue
            break

        if len(responses) < 2:
            raise MikrotikAPIError("Invalid response from API: too short message")

        return_values = []

        for response in responses.split(b'\x00')[:-1]:
            start = 0
            response = response.decode("utf-8")
            f = response.find("!")
            length = unpack_length(response[:f])
            response = response[f:]
            status = response[1:length]
            if status not in ['done', 'trap', 'fatal', 're']:
                raise MikrotikAPIError("Invalid response from API: invalid status %s" % status)
            if status == 'done':
                _type = MikrotikAPIResponseTypes.STATUS
            elif status == 're':
                _type = MikrotikAPIResponseTypes.DATA
            elif status in ['trap', 'fatal']:
                _type = MikrotikAPIResponseTypes.ERROR
            else:
                raise MikrotikAPIError("Got unknown error from API: %s" % response[length+1:])
            start += length
            length_length = 0
            data = {}
            errors = []
            while start < len(response):
                if (ord(response[start]) & 0x80) == 0:
                    length = unpack_length(response[start])
                    length_length = 1
                elif (ord(response[start]) & 0xC0) == 0x80:
                    length = unpack_length(response[start:start+1])
                    length_length = 2
                elif (ord(response[start]) & 0xE0) == 0xC0:
                    length = unpack_length(response[start:start+2])
                    length_length = 3
                elif (ord(response[start]) & 0xF0) == 0xE0:
                    length = unpack_length(response[start:start+3])
                    length_length = 4
                elif (ord(response[start]) & 0xF8) == 0xF0:
                    length = unpack_length(response[start:start+4])
                    length_length = 5
                start += length_length
                message = response[start:start+length]
                if message.startswith('='):
                    if message.startswith("=message="):
                        errors.append(message[9:])
                    else:
                        (k, v) = message[1:].split("=",1)
                        data.update({k: v})
                start += length
            return_values.append(MikrotikApiResponse(status=status, type=_type, error=errors, attributes=data))
        return return_values

    def login(self, username, password):
        r = MikrotikAPIRequest(command="/login")
        self._send(r.get_request())
        response = self._recv()[0]
        if 'ret' in response.attributes.keys():
            value = binascii.unhexlify(response.attributes['ret'])
            md = md5()
            md.update('\x00'.encode("utf-8"))
            md.update(password.encode("utf-8"))
            md.update(value)
            r = MikrotikAPIRequest(command="/login", attributes={'name': username, 'response': "00" + md.hexdigest()})
            self._send(r.get_request())
            self._recv()
            return
        raise MikrotikAPIError("Cannot log in!")

    def run(self, *args, **kwargs):
        r = MikrotikAPIRequest(*args, **kwargs)
        self._send(r.get_request())
        return self._recv()

    def disconnect(self):
        self._socket.shutdown(SHUT_WR)
        self._socket.close()
