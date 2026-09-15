import pytest

from apps.comments.forms import CommentForm
from apps.comments.models import COMMENT_MAX_LENGTH

pytestmark = pytest.mark.django_db


def test_an_empty_comment_is_refused():
    assert not CommentForm(data={"body": ""}).is_valid()


def test_a_comment_of_spaces_is_refused():
    assert not CommentForm(data={"body": "   \n\t  "}).is_valid()


def test_the_edges_are_trimmed():
    form = CommentForm(data={"body": "  Lovely light  "})

    assert form.is_valid()
    assert form.cleaned_data["body"] == "Lovely light"


def test_a_comment_at_the_ceiling_is_accepted():
    assert CommentForm(data={"body": "a" * COMMENT_MAX_LENGTH}).is_valid()


def test_a_comment_over_the_ceiling_is_refused():
    assert not CommentForm(data={"body": "a" * (COMMENT_MAX_LENGTH + 1)}).is_valid()


def test_a_nul_byte_never_reaches_the_database():
    """Postgres refuses the byte outright, and the error it raises there would
    arrive too late to be shown to anyone as a form error."""
    assert not CommentForm(data={"body": "Lovely\x00 light"}).is_valid()


def test_line_breaks_survive():
    """A comment is allowed to have paragraphs; only the edges are trimmed."""
    form = CommentForm(data={"body": "First line\nsecond line"})

    assert form.is_valid()
    assert form.cleaned_data["body"] == "First line\nsecond line"
