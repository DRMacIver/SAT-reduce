"""Command-line interface."""
import click


@click.command()
@click.version_option()
def main() -> None:
    """SAT-reduce."""


if __name__ == "__main__":
    main(prog_name="satreduce")  # pragma: no cover
