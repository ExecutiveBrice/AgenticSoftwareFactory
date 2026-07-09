from collections.abc import Callable

Command = Callable[..., None]


class Typer:
    def __init__(
        self, name: str | None = None, help: str | None = None, no_args_is_help: bool = False
    ) -> None:
        self.name = name
        self.help = help or ""
        self.commands: dict[str, Command] = {}
        self.no_args_is_help = no_args_is_help

    def command(self, name: str | None = None) -> Callable[[Command], Command]:
        def deco(fn: Command) -> Command:
            self.commands[name or fn.__name__.replace("_", "-")] = fn
            return fn

        return deco

    def __call__(self) -> None:
        import sys

        from typer.testing import CliRunner

        result = CliRunner().invoke(self, sys.argv[1:])
        print(result.output, end="")
        raise SystemExit(result.exit_code)


def echo(msg: object = "") -> None:
    print(msg)
