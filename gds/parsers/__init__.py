# -*- coding: utf-8 -*-
"""
GDS Parsers Package
===================

Parsers for GDS JSON database files.

Usage:
    from gds.parsers import GDSScheduleParser, GDSLibraryParser
"""

from gds.parsers.schedule_parser import GDSScheduleParser
from gds.parsers.library_parser import GDSLibraryParser

__all__ = ['GDSScheduleParser', 'GDSLibraryParser']
