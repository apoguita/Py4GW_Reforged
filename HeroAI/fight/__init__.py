"""Fight-zone positioning. Exports nothing on purpose — import exact submodules.

Mirrors the HeroAI/follow package rule: Core/GlobalCache/SharedMemory.py reaches
into that tree directly during startup, so a package-root import that pulls every
submodule is a startup hazard.
"""
