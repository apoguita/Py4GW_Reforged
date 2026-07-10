"""User-owned Launch Surface actions and feature providers.

Edit :func:`register_launch_surface_items` to expose project functionality on
the root Launch Surface. The framework imports this file explicitly; it does
not scan the repository for functions. Keep registration lightweight and put
the real feature import inside each callback so one optional feature cannot
prevent the launch surface from starting.
"""


def register_launch_surface_items(registry) -> None:
    """Register user-owned actions, window launchers, and components.

    Add entries inside this function. Every item needs a stable namespaced ID.
    The callback receives an invocation object with ``surface_id``,
    ``page_id``, ``item_id``, and ``context`` attributes.
    """

    # Example: call a project function.
    #
    # def open_my_feature(_invocation):
    #     from MyProject.feature import open_feature
    #
    #     open_feature()
    #
    # registry.register_action(
    #     'project:open_feature',
    #     'Open feature',
    #     open_my_feature,
    #     description='Opens the project feature.',
    #     category='Project',
    #     tags=('Project', 'Feature'),
    # )

    # Example: launch an existing widget-owned window or project panel.
    #
    # def show_my_window(_invocation):
    #     from MyProject.window import show_window
    #
    #     show_window()
    #
    # registry.register_window_launcher(
    #     'project:show_window',
    #     'Show project window',
    #     show_my_window,
    #     description='Shows the existing project window.',
    #     category='Project',
    # )

    return None
