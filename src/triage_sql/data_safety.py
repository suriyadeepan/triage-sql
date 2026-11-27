"""Helpers for keeping credential columns out of derived Azraq artifacts."""

from __future__ import annotations


SENSITIVE_COLUMNS = {"password"}


def prompt_columns(table: str, columns: list[str]) -> list[str]:
    """Return source columns allowed in prompts, indexes, and generated examples."""
    if table.casefold() != "users":
        return list(columns)
    return [column for column in columns if column.casefold() not in SENSITIVE_COLUMNS]


def sanitize_row(table: str, columns: list[str], row: list[str]) -> list[str]:
    """Replace sensitive source values with NULL-compatible empty fields."""
    if len(columns) != len(row):
        raise ValueError("row width does not match column header")
    if table.casefold() != "users":
        return list(row)
    return ["" if column.casefold() in SENSITIVE_COLUMNS else value for column, value in zip(columns, row)]
