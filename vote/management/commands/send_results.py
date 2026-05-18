from django.core.management.base import BaseCommand, CommandError

from vote.models import VotingSession
from vote.results_notifications import (
    build_final_results,
    send_session_results_notifications,
)


class Command(BaseCommand):
    help = "Send final results notifications for a closed voting session."

    def add_arguments(self, parser):
        parser.add_argument(
            "--session-id",
            type=int,
            help="VotingSession id. Defaults to the latest session.",
        )
        parser.add_argument(
            "--reset-flag",
            action="store_true",
            help="Reset sent flags before sending, useful for retrying a failed send.",
        )

    def handle(self, *args, **options):
        session_id = options.get("session_id")

        if session_id:
            session = VotingSession.objects.filter(id=session_id).first()
        else:
            session = VotingSession.objects.order_by("-start_datetime").first()

        if not session:
            raise CommandError("No voting session found.")

        if session.is_open():
            raise CommandError(f"Voting session {session.id} is still open.")

        if options["reset_flag"]:
            session.results_email_sent = False
            session.results_sms_sent = False
            session.save(update_fields=["results_email_sent", "results_sms_sent"])

        final_results = build_final_results(session)
        sent_counts = send_session_results_notifications(session, final_results)

        self.stdout.write(
            self.style.SUCCESS(
                "Session {id}: sent {email} email(s), {sms} SMS message(s).".format(
                    id=session.id,
                    email=sent_counts["email"],
                    sms=sent_counts["sms"],
                )
            )
        )
