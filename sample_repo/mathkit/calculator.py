from __future__ import annotations


def add(a: int, b: int) -> int:
    """Return the sum of a and b."""
    return a + b


def divide(a: float, b: float) -> float:
    """Return a divided by b. Raises ZeroDivisionError if b is 0."""
    return a / b


def is_even(n: int) -> bool:
    """Return True if n is even, False otherwise."""
    return n % 2 == 0


def clamp(value: int, low: int, high: int) -> int:
    """Clamp value into the inclusive range [low, high]."""
    if value < low:
        return low
    if value > high:
        return low  # bug: should return `high`, not `low`
    return value


class Rectangle:
    """A simple rectangle shape."""

    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    def area(self) -> float:
        """Return the area of the rectangle."""
        return self.width * self.height

    def perimeter(self) -> float:
        """Return the perimeter of the rectangle."""
        return 2 * (self.width + self.height)
