from django.contrib.auth.models import User
from django.utils import timezone

from .models import Candidate, Position, SchoolStudent, Vote
from .services import send_results_email, send_results_sms


def build_final_results(session):
    votes = Vote.objects.filter(
        voted_at__gte=session.start_datetime,
        voted_at__lte=session.end_datetime,
    ).select_related("candidate", "position")

    votes_by_candidate = {}
    votes_by_position = {}

    for vote in votes:
        votes_by_candidate[vote.candidate_id] = votes_by_candidate.get(vote.candidate_id, 0) + 1
        votes_by_position[vote.position_id] = votes_by_position.get(vote.position_id, 0) + 1

    final_results = []

    for position in Position.objects.all():
        candidates = Candidate.objects.filter(position=position)
        total_votes = votes_by_position.get(position.id, 0)
        candidate_results = []
        max_votes = 0

        for candidate in candidates:
            vote_count = votes_by_candidate.get(candidate.id, 0)
            max_votes = max(max_votes, vote_count)
            percentage = (vote_count / total_votes * 100) if total_votes else 0

            candidate_results.append({
                "id": candidate.id,
                "name": candidate.name,
                "party": candidate.party or "",
                "votes": vote_count,
                "percentage": round(percentage, 1),
                "photo": candidate.photo.url if candidate.photo else None,
            })

        winners = [
            candidate for candidate in candidate_results
            if candidate["votes"] == max_votes
        ] if max_votes > 0 else []

        final_results.append({
            "position": position.name,
            "candidates": candidate_results,
            "winners": winners,
            "winners_ids": [winner["id"] for winner in winners],
        })

    return final_results


def build_final_results_email_message(final_results, session):
    lines = [
        "Final school election results",
        f"Session: {timezone.localtime(session.start_datetime)} to {timezone.localtime(session.end_datetime)}",
    ]

    for result in final_results:
        lines.append("")
        lines.append(result["position"])

        for candidate in result["candidates"]:
            winner_marker = " - WINNER" if candidate["id"] in result["winners_ids"] else ""
            lines.append(
                f"{candidate['name']} - {candidate['votes']} votes "
                f"({candidate['percentage']}%){winner_marker}"
            )

    return "\n".join(lines)


def send_final_results_to_registered_voters(session, final_results):
    recipients = set()

    student_emails = SchoolStudent.objects.exclude(
        email__isnull=True,
    ).exclude(email="").values_list("email", flat=True)

    for email in student_emails:
        recipients.add(email.strip().lower())

    user_emails = User.objects.exclude(
        email__isnull=True,
    ).exclude(email="").values_list("email", flat=True)

    for email in user_emails:
        recipients.add(email.strip().lower())

    if not recipients:
        return 0

    message = build_final_results_email_message(final_results, session)
    sent_count = 0

    for email in recipients:
        if send_results_email(email, message):
            sent_count += 1

    return sent_count


def build_final_results_sms_message(final_results):
    lines = ["Final election results:"]

    for result in final_results:
        winners = result.get("winners") or []

        if winners:
            winner_names = ", ".join(winner["name"] for winner in winners)
            winner_votes = winners[0]["votes"]
            lines.append(f"{result['position']}: {winner_names} ({winner_votes} votes)")
            continue

        lines.append(f"{result['position']}: No winner")

    return "\n".join(lines)


def send_final_results_to_ussd_voters(session, final_results):
    phones = set()
    voter_phones = Vote.objects.filter(
        voted_at__gte=session.start_datetime,
        voted_at__lte=session.end_datetime,
    ).exclude(phone__isnull=True).exclude(phone="").values_list("phone", flat=True)

    for phone in voter_phones:
        phones.add(phone.strip())

    if not phones:
        return 0

    message = build_final_results_sms_message(final_results)
    sent_count = 0

    for phone in phones:
        if send_results_sms(phone, message):
            sent_count += 1

    return sent_count


def send_session_results_notifications(session, final_results=None):
    if session.is_open():
        return {"email": 0, "sms": 0}

    final_results = final_results or build_final_results(session)
    update_fields = []
    sent_counts = {"email": 0, "sms": 0}

    if not session.results_email_sent:
        sent_counts["email"] = send_final_results_to_registered_voters(session, final_results)

        if sent_counts["email"]:
            session.results_email_sent = True
            update_fields.append("results_email_sent")

    if not session.results_sms_sent:
        sent_counts["sms"] = send_final_results_to_ussd_voters(session, final_results)

        if sent_counts["sms"]:
            session.results_sms_sent = True
            update_fields.append("results_sms_sent")

    if update_fields:
        session.save(update_fields=update_fields)

    return sent_counts
