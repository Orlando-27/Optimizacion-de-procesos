"""Adaptadores de I/O: interfaces genericas + implementaciones intercambiables.

Regla de oro: el proceso depende SOLO de las interfaces base (``MailClient``,
``Storage``, ``ExcelRunner``). Cambiar de Windows/COM a GCP = cambiar la
implementacion concreta que se inyecta, sin tocar la logica del proceso.
"""
