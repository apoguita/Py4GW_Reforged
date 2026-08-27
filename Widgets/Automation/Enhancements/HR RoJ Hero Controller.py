"""Always-on low-overhead RoJ Hero controller.

Enable this widget together with HeroAI on the account that owns the Monk heroes.
It does not draw a window; it only coordinates the owned RoJ heroes.
"""
from Py4GWCoreLib.Builds.Skills import HeroClusterCoordinator
from Py4GWCoreLib.Builds.Skills import RoJMonkHeroController

MODULE_NAME = "HR RoJ Hero Controller"

def main():
    try:
        HeroClusterCoordinator.run(enabled=True)
        RoJMonkHeroController.run(enabled=True)
    except Exception:
        # Controller itself event-logs detailed errors. Keep the widget fail-safe.
        pass

def configure():
    pass
