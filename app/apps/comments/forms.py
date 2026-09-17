from django import forms

from .models import Comment


class CommentForm(forms.ModelForm):
    """The one field a visitor fills in. Who wrote it, under which picture and
    in answer to what are put on the instance by the view.

    Nothing is validated by hand: the form field built from the model already
    trims the edges, measures what is left against the ceiling, refuses a text
    that turns out empty and turns away the NUL byte Postgres cannot store.
    """

    class Meta:
        model = Comment
        fields = ["body"]
        error_messages = {"body": {"required": "Write something first"}}
