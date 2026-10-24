"""Seed a small demo campus so the whole loop can be clicked through."""

import datetime as dt

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from campus.models import College, StudentProfile

User = get_user_model()

STUDENTS = [
    ("Aman Kumar", "23BCA104", "BCA", 2, "A", "male"),
    ("Priya Singh", "23BCA107", "BCA", 2, "A", "female"),
    ("Nikita Sharma", "23BCA127", "BCA", 2, "B", "female"),
    ("Rohan Verma", "23BCA112", "BCA", 2, "B", "male"),
    ("Aisha Khan", "24BCA031", "BCA", 1, "A", "female"),
]


class Command(BaseCommand):
    help = "Create a demo college plus a handful of verified campus identities."

    def add_arguments(self, parser):
        parser.add_argument("--college", default="ABC College")
        parser.add_argument("--password", default="campus-demo-123")

    @transaction.atomic
    def handle(self, *args, **options):
        college, _ = College.objects.get_or_create(
            name=options["college"], defaults={"city": "Patna", "state": "Bihar"}
        )
        today = dt.date.today()
        created = []

        for index, (name, roll, course, year, section, gender) in enumerate(STUDENTS, start=1):
            email = f"{roll.lower()}@example.edu"
            user, _ = User.objects.get_or_create(
                username=email,
                defaults={"email": email, "first_name": name.split(" ")[0]},
            )
            user.set_password(options["password"])
            user.save()
            student, _ = StudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    "college": college,
                    "full_name": name,
                    "roll_number": roll,
                    "course": course,
                    "year": year,
                    "section": section,
                    "gender": gender,
                    "date_of_birth": today.replace(year=today.year - 20),
                    "is_verified": True,
                },
            )
            created.append(student)

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(created)} campus identities ready at {college.name}. "
                f"Sign in with any roll (e.g. 23BCA104@ / {options['password']})."
            )
        )
        self.stdout.write("Run `manage.py seed_match` to create a mutual crush.")