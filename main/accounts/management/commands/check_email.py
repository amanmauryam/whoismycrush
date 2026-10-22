"""Diagnose the email setup: is SMTP reachable, are the credentials valid, and
does a real message actually go out?

The app used to hide every one of these failures behind ``fail_silently=True``,
so a broken mail server looked exactly like a working one. This command makes
the same settings visible from the terminal.

    python manage.py check_email
    python manage.py check_email --to you@example.com
"""

from __future__ import annotations

import base64
import smtplib
import ssl

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.management.base import BaseCommand, CommandError


def _probe_smtp() -> str:
    """Re-run the login by hand to recover the server's own error message.

    Providers such as Gmail hang up during authentication instead of returning
    a clean error, which makes Python raise a bare
    ``SMTPServerDisconnected``. Doing the ``AUTH LOGIN`` exchange manually gets
    the real response code (usually ``535``) back.
    """
    user = settings.EMAIL_HOST_USER
    password = settings.EMAIL_HOST_PASSWORD
    last = "no response from the server"
    connection = None
    try:
        connection = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=15)
        connection.ehlo()
        if settings.EMAIL_USE_TLS or settings.EMAIL_USE_SSL:
            connection.starttls(context=ssl.create_default_context())
        connection.ehlo()

        for payload in (
            "LOGIN",
            base64.b64encode(user.encode()).decode(),
            base64.b64encode(password.encode()).decode(),
        ):
            code, response = connection.docmd("AUTH", "LOGIN") if payload == "LOGIN" \
                else connection.docmd(payload)
            text = response.decode(errors="replace") if isinstance(response, bytes) else str(response)
            last = f"SMTP {code}: {text.strip()}"
            if code >= 400:
                break
    except Exception as exc:
        last = f"{last} (then {type(exc).__name__}: {exc})"
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
    return last


class Command(BaseCommand):
    help = "Check the SMTP configuration and optionally send a test email."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            dest="to",
            default="",
            help="Send a real test email to this address.",
        )

    def handle(self, *args, **options):
        backend = settings.EMAIL_BACKEND
        self.stdout.write(f"EMAIL_BACKEND       : {backend}")

        if "smtp" not in backend:
            self.stdout.write(
                self.style.WARNING(
                    "This is not an SMTP backend, so no mail leaves this machine."
                )
            )
            self.stdout.write(
                "Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend "
                "to send real email."
            )
            return

        self.stdout.write(f"EMAIL_HOST          : {settings.EMAIL_HOST}")
        self.stdout.write(f"EMAIL_PORT          : {settings.EMAIL_PORT}")
        self.stdout.write(f"EMAIL_USE_TLS       : {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"EMAIL_USE_SSL       : {settings.EMAIL_USE_SSL}")
        self.stdout.write(f"EMAIL_HOST_USER     : {settings.EMAIL_HOST_USER or '<none>'}")
        self.stdout.write(
            f"EMAIL_HOST_PASSWORD : {'set' if settings.EMAIL_HOST_PASSWORD else '<missing>'}"
        )
        self.stdout.write(f"DEFAULT_FROM_EMAIL  : {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"SITE_URL            : {settings.SITE_URL}")

        if not settings.EMAIL_HOST_USER:
            self.stdout.write(
                self.style.WARNING(
                    "EMAIL_HOST_USER is empty. Gmail and most providers need a "
                    "username and an app password."
                )
            )

        connection = get_connection()
        try:
            connection.open()
        except Exception as exc:
            detail = _probe_smtp()
            raise CommandError(
                f"Could not connect to {settings.EMAIL_HOST}:{settings.EMAIL_PORT} "
                f"as {settings.EMAIL_HOST_USER or '<anonymous>'}.\n"
                f"  Django said: {type(exc).__name__}: {exc}\n"
                f"  Server said: {detail}\n\n"
                "If the server answered 535, the username or password is wrong.\n"
                "For Gmail that almost always means: 2-Step Verification is off, or "
                "the app password was revoked. Turn on 2-Step Verification, then "
                "create a fresh app password at "
                "https://myaccount.google.com/apppasswords and put it in "
                "EMAIL_HOST_PASSWORD."
            ) from exc

        self.stdout.write(self.style.SUCCESS("Connected and authenticated."))

        recipient = (options.get("to") or "").strip()
        if not recipient:
            self.stdout.write("No --to given, so no test message was sent.")
            return

        message = EmailMessage(
            "WhoIsMyCrush email test",
            "This is a test message from `manage.py check_email`. "
            "If you can read it, outbound email is working.",
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
        )
        try:
            sent = message.send(connection)
        except Exception as exc:
            raise CommandError(
                f"Connected fine, but sending to {recipient} failed.\n"
                f"  {type(exc).__name__}: {exc}"
            ) from exc

        if sent:
            self.stdout.write(self.style.SUCCESS(f"Sent a test email to {recipient}."))
        else:
            raise CommandError(f"The server did not accept the message for {recipient}.")
