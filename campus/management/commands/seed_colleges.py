"""Seed campuses so the picker is not empty on a fresh install."""

from django.core.management.base import BaseCommand
from django.db import transaction

from campus.models import College

COLLEGES = [
    ("ABC College", "Patna", "Bihar", ""),
    ("XYZ University", "Delhi", "Delhi", ""),
    ("DEF College", "Kanpur", "Uttar Pradesh", ""),
    ("University of Mumbai", "Mumbai", "Maharashtra", "mu.ac.in"),
    ("Anna University", "Chennai", "Tamil Nadu", "annauniv.edu"),
    ("Jadavpur University", "Kolkata", "West Bengal", "jadavpur.ac.in"),
    ("Delhi University", "New Delhi", "Delhi", "du.ac.in"),
    ("Panjab University", "Chandigarh", "Punjab", "puchd.ac.in"),
    ("University of Hyderabad", "Hyderabad", "Telangana", "uohyd.ac.in"),
    ("BHU", "Varanasi", "Uttar Pradesh", "bhu.ac.in"),
    ("Lovely Professional University", "Phagwara", "Punjab", "lpu.in"),
    ("SRM Institute of Science and Technology", "Chennai", "Tamil Nadu", "srmap.edu.in"),
]


class Command(BaseCommand):
    help = "Create the starter list of campuses."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Remove campuses that are not in the starter list.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for name, city, state, domain in COLLEGES:
            _obj, was_created = College.objects.get_or_create(
                name=name,
                defaults={"city": city, "state": state, "domain": domain},
            )
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(f"Campuses ready ({created} new, {College.objects.count()} total).")
        )

        if options["flush"]:
            removed, _ = College.objects.exclude(name__in=[c[0] for c in COLLEGES]).delete()
            self.stdout.write(self.style.WARNING(f"Removed {removed} extra campus records."))