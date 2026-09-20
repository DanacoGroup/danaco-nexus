"""Piaskownica demonstracyjna „Wypróbuj teraz”: sesje gościa bez konta.

Gość dostaje krótkożyjącą sesję w pamięci procesu API, własny katalog roboczy
poza magazynem plików użytkownika i twarde limity. Uruchamia gotowe scenariusze
zbudowane z narzędzi agenta; gdy serwer nie ma modelu albo programów danego
scenariusza, przebieg jest odtwarzany z nagrania i tak oznaczony w interfejsie.
"""

from __future__ import annotations
