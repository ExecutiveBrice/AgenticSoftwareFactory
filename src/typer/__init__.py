# mypy: ignore-errors
class Typer:
    def __init__(self, name=None, help=None, no_args_is_help=False):
        self.name = name
        self.help = help or ""
        self.commands = {}
        self.no_args_is_help = no_args_is_help

    def command(self, name=None):
        def deco(fn):
            self.commands[name or fn.__name__.replace("_", "-")] = fn
            return fn

        return deco

    def __call__(self) -> None:
        import sys

        from typer.testing import CliRunner

        result = CliRunner().invoke(self, sys.argv[1:])
        print(result.output, end="")
        raise SystemExit(result.exit_code)


def echo(msg=""):
    print(msg)
