from __future__ import annotations


def tabulate(rows: list[list[str]], headers: list[str], tablefmt: str = "simple") -> str:
    if tablefmt != "github":
        raise ValueError("This local tabulate implementation only supports github format")

    normalized_rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(str(header)) for header in headers]
    for row in normalized_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def render_row(row: list[str]) -> str:
        cells = [f" {value.ljust(widths[index])} " for index, value in enumerate(row)]
        return f"|{'|'.join(cells)}|"

    header_row = render_row([str(header) for header in headers])
    separator = "|" + "|".join(f"{'-' * (width + 2)}" for width in widths) + "|"
    body = [render_row(row) for row in normalized_rows]
    return "\n".join([header_row, separator, *body])
