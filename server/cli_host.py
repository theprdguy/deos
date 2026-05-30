"""Host-level CLI command registration (projects registry, overview, feedback, open).

These operate on the host OS itself (no `--project`), so their argparse wiring lives
here rather than bloating server/cli.py. Called once from cli._build_parser().
"""
from __future__ import annotations


def add_host_commands(sub) -> None:
    """Register host-level subcommands on the given argparse subparsers object."""
    from server.feedback import handle_feedback
    from server.launcher import handle_open
    from server.overview import handle_overview
    from server.projects_registry import handle_projects, handle_register

    p_reg = sub.add_parser("register", help="Register a project in the host registry")
    p_reg.add_argument("name", metavar="<name>")
    p_reg.add_argument("repo_path", metavar="<repo-path>")
    p_reg.add_argument("--status", default="active")
    p_reg.set_defaults(handler=handle_register)

    sub.add_parser("projects", help="List registered projects").set_defaults(
        handler=handle_projects
    )
    sub.add_parser(
        "overview", help="Cross-project status (todo/doing/blocked)"
    ).set_defaults(handler=handle_overview)

    p_fb = sub.add_parser("feedback", help="Append an OS-feedback entry to the host inbox")
    p_fb.add_argument("text", metavar="<text>")
    p_fb.set_defaults(handler=handle_feedback)

    p_open = sub.add_parser("open", help="Open a project session (claude + host settings)")
    p_open.add_argument("name", metavar="<name>")
    p_open.add_argument(
        "--print",
        dest="print_cmd",
        action="store_true",
        help="Print the launch command instead of exec'ing it",
    )
    p_open.set_defaults(handler=handle_open)
