====
Mikrotik API
====

.. image:: https://drone.io/github.com/annttu/Mikrotik/status.png

Mikrotik-API is a python client library for Mikrotik API.

Currently library supports python >= 2.7

Usage
-----

Example::

    >>> import mikrotik
    >>> m = mikrotik.Mikrotik("10.0.0.1")
    >>> m.login("user", "pass")
    >>> m.run("/ip/address/print")


