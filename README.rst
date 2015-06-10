====
Mikrotik API
====

.. image:: https://drone.io/github.com/annttu/Mikrotik-api/status.png

Mikrotik-API is a python client library for Mikrotik API.

Currently library supports python >= 2.7

Usage
-----

Example::

    >>> import mikrotik
    >>> m = mikrotik.Mikrotik()
    >>> m.login("user", "pass")
    >>> m.run("/ip/address/print")


