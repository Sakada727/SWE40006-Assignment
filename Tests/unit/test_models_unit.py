import pytest

from models import MAX_TITLE_LENGTH, Task, validate_title


def test_validate_title_strips_surrounding_whitespace():
    assert validate_title("  Buy milk  ") == "Buy milk"


@pytest.mark.parametrize("bad_value", [None, "", "   ", 123])
def test_validate_title_rejects_missing_or_blank_values(bad_value):
    with pytest.raises(ValueError):
        validate_title(bad_value)


def test_validate_title_accepts_exactly_the_maximum_length():
    title = "a" * MAX_TITLE_LENGTH
    assert validate_title(title) == title


def test_validate_title_rejects_titles_over_the_maximum_length():
    with pytest.raises(ValueError, match="at most"):
        validate_title("a" * (MAX_TITLE_LENGTH + 1))


def test_task_to_dict_exposes_the_public_fields():
    task = Task(title="Write report", done=False)
    assert task.to_dict() == {
        "id": None,
        "title": "Write report",
        "done": False,
        "created_at": None,
    }