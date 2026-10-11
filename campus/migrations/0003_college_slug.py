"""Add ``College.slug`` and backfill it for every existing campus.

Slugs are the stable, readable public handle used by the shareable
``/college/<slug>/`` and ``/join/<slug>/`` links (growth). Unique from the
start, with existing rows made unique by ``_unique_slug`` logic reproduced
here.

The field is added unique=False first with a defaults backfill, then made
unique, because a data migration cannot run against a ``unique=True`` column
that starts empty.
"""

from django.db import migrations, models
from django.utils.text import slugify


def backfill_slugs(apps, schema_editor):
    College = apps.get_model("campus", "College")
    taken: set[str] = set()
    for college in College.objects.all().order_by("pk"):
        base = slugify(college.name)[:180] or "campus"
        candidate = base
        suffix = 2
        while candidate in taken:
            candidate = f"{base}-{suffix}"
            suffix += 1
        college.slug = candidate
        college.save(update_fields=["slug"])
        taken.add(candidate)


class Migration(migrations.Migration):
    dependencies = [
        ("campus", "0002_remove_studentprofile_is_hidden_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="college",
            name="slug",
            field=models.SlugField(
                blank=True,
                default="",
                help_text="Public URL fragment, derived from the name.",
                max_length=200,
            ),
        ),
        migrations.RunPython(backfill_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="college",
            name="slug",
            field=models.SlugField(
                blank=True,
                help_text="Public URL fragment, derived from the name.",
                max_length=200,
                unique=True,
            ),
        ),
    ]