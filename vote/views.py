# views.py
from .models import VotingSession
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from .forms import StudentRegisterForm
from .models import SchoolStudent, Candidate, Position, Vote, Comment
from django.contrib import messages
from django.contrib.auth.models import User
from datetime import datetime, date, time, timedelta
import secrets
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.hashers import make_password, check_password
from .models import SchoolStudent
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from .services import (
    VOTE_CONFIRMATION_MESSAGE,
    VoteSubmissionError,
    listen,
    match_candidate,
    send_login_verification_code,
    send_results_email,
    send_sms,
    send_vote_confirmation,
    speak,
    submit_vote,
)


def add_registration_email_field(form):
    from django import forms

    form.fields["email"] = forms.EmailField(required=True)
    return form


def clean_gmail_address(email, admission_number=None):
    email = (email or "").strip().lower()

    if not email:
        raise ValidationError("Email is required for online voters.")

    validate_email(email)

    if not email.endswith("@gmail.com"):
        raise ValidationError("Only Gmail addresses are allowed.")

    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError("This email is already registered.")

    student_email_exists = SchoolStudent.objects.filter(email__iexact=email)
    if admission_number:
        student_email_exists = student_email_exists.exclude(admission_number=admission_number)

    if student_email_exists.exists():
        raise ValidationError("This email is already registered.")

    return email


def build_student_user(student):
    if student.user:
        return student.user

    if not student.email:
        return None

    names = student.full_name.strip().split()
    user = User.objects.filter(username=student.admission_number).first()

    if not user:
        user = User.objects.create_user(
            username=student.admission_number,
            email=student.email,
            password=None,
            first_name=names[0] if names else "",
            last_name=" ".join(names[1:]) if len(names) > 1 else "",
        )
        user.set_unusable_password()
        user.save()

    student.user = user
    student.save(update_fields=["user"])
    return user


def get_login_email(user):
    email = (getattr(user, "email", "") or "").strip()
    if email:
        return email

    student = SchoolStudent.objects.filter(user=user).first()
    return (student.email or "").strip() if student else ""


def begin_two_step_login(request, user):
    email = get_login_email(user)

    if not email:
        return False

    code = f"{secrets.randbelow(1000000):06d}"
    expires_at = timezone.now() + timedelta(minutes=10)

    if not send_login_verification_code(email, code):
        return False

    request.session["pending_login_user_id"] = user.id
    request.session["pending_login_code"] = code
    request.session["pending_login_expires_at"] = expires_at.isoformat()
    request.session["pending_login_email"] = email
    return True


def complete_two_step_login(request, code):
    pending_user_id = request.session.get("pending_login_user_id")
    pending_code = request.session.get("pending_login_code")
    expires_at_value = request.session.get("pending_login_expires_at")

    if not pending_user_id or not pending_code or not expires_at_value:
        return None, "Your login code session expired. Please log in again."

    try:
        expires_at = datetime.fromisoformat(expires_at_value)
    except ValueError:
        return None, "Your login code session expired. Please log in again."

    if timezone.is_naive(expires_at):
        expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())

    if timezone.now() > expires_at:
        clear_pending_login(request)
        return None, "Your login code expired. Please log in again."

    if (code or "").strip() != pending_code:
        return None, "Invalid verification code."

    user = User.objects.filter(id=pending_user_id).first()

    if not user:
        clear_pending_login(request)
        return None, "Account not found. Please log in again."

    clear_pending_login(request)
    return user, None


def clear_pending_login(request):
    for key in (
        "pending_login_user_id",
        "pending_login_code",
        "pending_login_expires_at",
        "pending_login_email",
    ):
        request.session.pop(key, None)

# -----------------------------
# Home page
# -----------------------------
def home(request):
    return render(request, 'vote/home.html')


# -----------------------------
# Student registration
# -----------------------------
from django.contrib.auth.hashers import make_password
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.contrib.auth.models import User

from .models import SchoolStudent


def student_register(request):
    if request.method == "POST":
        form = add_registration_email_field(StudentRegisterForm(request.POST))

        if form.is_valid():

            admission_number = form.cleaned_data['admission_number'].strip()
            email = form.cleaned_data['email'].strip().lower()
            password = form.cleaned_data['password1']
            pin = form.cleaned_data['pin'].strip()

            try:
                email = clean_gmail_address(email, admission_number)
            except ValidationError as exc:
                form.add_error("email", exc)
                return render(request, 'vote/register.html', {'form': form})

            # =========================
            # PIN VALIDATION (IMPORTANT FIX)
            # =========================
            if len(pin) != 4 or not pin.isdigit():
                form.add_error("pin", "PIN must be exactly 4 digits.")
                return render(request, 'vote/register.html', {'form': form})

            # =========================
            # CHECK SCHOOL RECORD
            # =========================
            try:
                school_student = SchoolStudent.objects.get(
                    admission_number=admission_number
                )
            except SchoolStudent.DoesNotExist:
                form.add_error(None, "Admission number not found.")
                return render(request, 'vote/register.html', {'form': form})

            # =========================
            # ALREADY REGISTERED CHECK
            # =========================
            if school_student.user:
                form.add_error(None, "Already registered.")
                return render(request, 'vote/register.html', {'form': form})

            if User.objects.filter(username=admission_number).exists():
                form.add_error(None, "User already exists.")
                return render(request, 'vote/register.html', {'form': form})

            # =========================
            # CREATE USER
            # =========================
            names = school_student.full_name.strip().split()
            first_name = names[0] if names else ""
            last_name = " ".join(names[1:]) if len(names) > 1 else ""

            user = User.objects.create_user(
                username=admission_number,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            user.is_active = True
            user.save()

            # =========================
            # LINK + SAVE PIN
            # =========================
            school_student.user = user
            school_student.email = email
            school_student.pin = make_password(pin)
            school_student.is_ussd_registered = True
            school_student.save()

            # =========================
            # LOGIN USER
            # =========================
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)

            return redirect('vote_page')

    else:
        form = add_registration_email_field(StudentRegisterForm())

    return render(request, 'vote/register.html', {'form': form})
# -----------------------------
# Student login
# -----------------------------
def student_login(request):
    if request.method == "POST":
        if request.POST.get("login_step") == "verify_code":
            code = request.POST.get("verification_code", "").strip()
            user, error = complete_two_step_login(request, code)

            if error:
                return render(request, 'vote/login.html', {
                    'error': error,
                    'show_code_form': True,
                    'pending_email': request.session.get("pending_login_email"),
                })

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('vote_page')

        adm = request.POST.get('admission_number', '').strip()
        password = request.POST.get('password', '').strip()
        pin = request.POST.get('pin', '').strip()

        user = authenticate(request, username=adm, password=password)

        # CASE 1: LOGIN WITH PASSWORD
        if user:
            if begin_two_step_login(request, user):
                return render(request, 'vote/login.html', {
                    'show_code_form': True,
                    'pending_email': request.session.get("pending_login_email"),
                    'message': "A verification code has been sent to your email.",
                })

            return render(request, 'vote/login.html', {
                'error': "Could not send a verification code. Check that your email settings and registered email are correct."
            })

        # CASE 2: LOGIN WITH PIN (fallback)
        student = SchoolStudent.objects.filter(admission_number=adm).first()

        if student and student.pin:
            if pin and student.check_pin(pin):
                user = build_student_user(student)

                if not user:
                    return render(request, 'vote/login.html', {
                        'error': "PIN is correct, but no email is registered for this admission number. Please register online or ask the admin to add your email."
                    })

                if begin_two_step_login(request, user):
                    return render(request, 'vote/login.html', {
                        'show_code_form': True,
                        'pending_email': request.session.get("pending_login_email"),
                        'message': "A verification code has been sent to your email.",
                    })

                return render(request, 'vote/login.html', {
                    'error': "Could not send a verification code. Check that your email settings and registered email are correct."
                })

        return render(request, 'vote/login.html', {
            'error': "Invalid credentials"
        })

    return render(request, 'vote/login.html')





from django.utils import timezone

@login_required
def vote_page(request):
    user = request.user

    session = VotingSession.objects.filter(active=True)\
        .order_by('-start_datetime').first()

    if not session:
        return render(request, 'vote/closed.html', {
            'message': 'No active voting session found.',
            'session': None
        })

    if not session.is_open():
        return render(request, 'vote/closed.html', {
            'message': 'Voting is currently closed.',
            'session': session
        })

    # 🔥 STRICT: if user already voted ANY position
    if Vote.objects.filter(user=user).exists():
        return redirect('results_page')

    # 🔥 FIX: preload positions + candidates correctly
    positions = Position.objects.prefetch_related('candidate_set').all()

    if request.method == "POST":

        # re-check session on submit
        if not session.is_open():
            return render(request, 'vote/closed.html', {
                'message': 'Voting closed while submitting.',
                'session': session
            })

        student = SchoolStudent.objects.filter(user=user).first()
        phone = request.POST.get("phone") or (student.phone if student else None)
        voted_any = False

        for position in positions:
            candidate_id = request.POST.get(f'position_{position.id}')

            if candidate_id:

                try:
                    candidate = Candidate.objects.get(
                        id=candidate_id,
                        position=position
                    )
                except Candidate.DoesNotExist:
                    continue

                try:
                    submit_vote(
                        candidate=candidate,
                        user=user,
                        phone=phone,
                        send_notifications=False,
                    )
                    voted_any = True
                except VoteSubmissionError:
                    continue

        if voted_any:
            if student and phone and student.phone != phone:
                student.phone = phone
                student.save(update_fields=["phone"])

            send_vote_confirmation(user=user, phone=phone)

        return redirect('results_page')

    return render(request, 'vote/vote_page.html', {
        'positions': positions,
        'session': session,
        'session_end': session.end_datetime
    })


@login_required
def voice_vote_view(request):
    user = request.user
    student = SchoolStudent.objects.filter(user=user).first()
    phone = student.phone if student else None

    session = get_active_session()

    if not session or not session.is_open():
        if request.method == "POST":
            return JsonResponse({"ok": False, "message": "Voting is currently closed."}, status=400)

        return render(request, 'vote/closed.html', {
            'message': 'Voting is currently closed.',
            'session': session
        })

    if request.method == "POST":
        candidate_ids = request.POST.getlist("candidate_ids")

        if not candidate_ids:
            return JsonResponse({"ok": False, "message": "No candidates selected."}, status=400)

        remaining_positions = [
            position for position in Position.objects.order_by("id")
            if not Vote.has_voted(user=user, phone=phone, position=position)
        ]

        candidates = Candidate.objects.select_related("position").filter(id__in=candidate_ids)
        candidates_by_position = {candidate.position_id: candidate for candidate in candidates}

        missing_positions = [
            position.name for position in remaining_positions
            if position.id not in candidates_by_position
        ]

        if missing_positions:
            return JsonResponse({
                "ok": False,
                "message": "Please vote for all positions before submitting.",
                "missing_positions": missing_positions,
            }, status=400)

        try:
            with transaction.atomic():
                for position in remaining_positions:
                    submit_vote(
                        candidate=candidates_by_position[position.id],
                        user=user,
                        phone=phone,
                        send_notifications=False,
                    )
        except VoteSubmissionError as exc:
            return JsonResponse({"ok": False, "message": str(exc)}, status=400)

        send_vote_confirmation(user=user, phone=phone)

        return JsonResponse({
            "ok": True,
            "message": "All votes have been successfully recorded.",
        })

    voice_positions = []

    for position in Position.objects.prefetch_related("candidate_set").order_by("id"):
        if Vote.has_voted(user=user, phone=phone, position=position):
            continue

        candidates = [
            {
                "id": candidate.id,
                "name": candidate.name,
                "number": index,
            }
            for index, candidate in enumerate(position.candidate_set.all().order_by("id"), 1)
        ]

        if candidates:
            voice_positions.append({
                "id": position.id,
                "name": position.name,
                "candidates": candidates,
            })

    return render(request, 'vote/voice_vote.html', {
        "voice_positions": voice_positions,
        "session": session,
    })

@login_required
def results_page(request):

    positions = Position.objects.all()
    results = []

    # 🔥 ACTIVE SESSION (clean)
    session = VotingSession.objects.filter(active=True)\
        .order_by('-start_datetime').first()

    # 🔥 OPTIMIZED VOTE FETCH (fast + safe)
    votes_by_candidate = {}
    votes_by_position = {}

    for vote in Vote.objects.select_related("candidate", "position"):
        votes_by_candidate[vote.candidate_id] = votes_by_candidate.get(vote.candidate_id, 0) + 1
        votes_by_position[vote.position_id] = votes_by_position.get(vote.position_id, 0) + 1

    # 🔥 BUILD RESULTS
    for position in positions:

        candidates = Candidate.objects.filter(position=position)

        total_votes = votes_by_position.get(position.id, 0)

        candidate_results = []

        for candidate in candidates:

            vote_count = votes_by_candidate.get(candidate.id, 0)

            percentage = (vote_count / total_votes * 100) if total_votes else 0

            candidate_results.append({
                'name': (
                    f"{candidate.name} & {candidate.deputy_name}"
                    if candidate.deputy_name else candidate.name
                ),
                'party': candidate.party or '',
                'votes': vote_count,
                'percentage': round(percentage, 1),
                'photo': candidate.photo.url if candidate.photo else None
            })

        results.append({
            'position': position.name,
            'candidates': candidate_results
        })

    # 🔥 SAFE TIMESTAMP
    session_end_datetime = None

    if session:
        session_end_datetime = session.end_datetime

    return render(request, 'vote/results.html', {
        'results': results,
        'session': session,
        'session_end': session_end_datetime
    })



def close(request):
    return render(request, 'vote/closed.html')


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

    for email in SchoolStudent.objects.exclude(email__isnull=True).exclude(email="").values_list("email", flat=True):
        recipients.add(email.strip().lower())

    for email in User.objects.exclude(email__isnull=True).exclude(email="").values_list("email", flat=True):
        recipients.add(email.strip().lower())

    if not recipients:
        return 0

    message = build_final_results_email_message(final_results, session)
    sent_count = 0

    for email in recipients:
        if send_results_email(email, message):
            sent_count += 1

    return sent_count


def final_results_page(request):

    # -----------------------------
    # ACTIVE SESSION
    # -----------------------------
    session = VotingSession.objects.order_by('-start_datetime').first()

    if not session:
        return render(request, 'vote/final_results.html', {
            "final_results": [],
            "comments": [],
            "error_message": "No voting session found."
        })

    # If voting still ongoing
    if session.is_open():
        return render(request, 'vote/results.html', {
            'voting_message': "Voting is still ongoing. Final results are not ready.",
            'session': session
        })

    # -----------------------------
    # COMMENTS
    # -----------------------------
    error_message = None

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect('login')

        message = request.POST.get('message')
        adm_number = request.POST.get('adm_number')

        student = SchoolStudent.objects.filter(user=request.user).first()

        if not message or not adm_number:
            error_message = "Please fill all fields."

        elif not student or adm_number != student.admission_number:
            error_message = "Invalid admission number."

        else:
            Comment.objects.create(
                user=request.user,
                adm_number=adm_number,
                message=message
            )
            return redirect('final_results_page')

    # -----------------------------
    # FILTERED VOTES (SESSION SAFE FIX)
    # -----------------------------
    votes = Vote.objects.filter(
        voted_at__gte=session.start_datetime,
        voted_at__lte=session.end_datetime
    ).select_related("candidate", "position")

    votes_by_candidate = {}
    votes_by_position = {}

    for vote in votes:
        votes_by_candidate[vote.candidate_id] = votes_by_candidate.get(vote.candidate_id, 0) + 1
        votes_by_position[vote.position_id] = votes_by_position.get(vote.position_id, 0) + 1

    # -----------------------------
    # BUILD RESULTS
    # -----------------------------
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
            c for c in candidate_results if c["votes"] == max_votes
        ] if max_votes > 0 else []

        winner_ids = [w["id"] for w in winners]

        final_results.append({
            "position": position.name,
            "candidates": candidate_results,
            "winners": winners,
            "winners_ids": winner_ids
        })

    comments = Comment.objects.all().order_by('-timestamp')

    if not session.results_email_sent:
        sent_count = send_final_results_to_registered_voters(session, final_results)

        if sent_count:
            session.results_email_sent = True
            session.save(update_fields=["results_email_sent"])

    return render(request, 'vote/final_results.html', {
        "final_results": final_results,
        "comments": comments,
        "error_message": error_message,
        "session": session
    })





from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.contrib.auth.hashers import make_password

from .models import SchoolStudent, Position, Candidate, Vote, VotingSession


# =========================
# HELPERS
# =========================
def safe_int(value):
    try:
        return int(value)
    except:
        return None


def is_authenticated(student, pin):
    if not student or not pin:
        return False
    return student.check_pin(pin)


def get_active_session():
    return VotingSession.objects.filter(active=True).order_by('-start_datetime').first()


# =========================
# USSD VIEW (FINAL)
# =========================
@csrf_exempt
def ussd_callback(request):

    try:
        text = request.POST.get('text') or request.GET.get('text') or ''
        phone = request.POST.get('phoneNumber') or request.GET.get('phoneNumber') or ''

        text = text.strip()
        parts = text.split("*") if text else []

        adm = parts[0] if len(parts) > 0 else None
        pin = parts[1] if len(parts) > 1 else None

        student = SchoolStudent.objects.filter(admission_number=adm).first() if adm else None

        session = get_active_session()

        # =========================
        # SESSION CHECK
        # =========================
        if not session or not session.is_open():
            return HttpResponse("END Voting closed", content_type="text/plain")

        # =========================
        # STEP 1: ENTER ADM
        # =========================
        if text == "":
            return HttpResponse("CON Enter Admission Number", content_type="text/plain")

        # =========================
        # STEP 2: CHECK STUDENT
        # =========================
        if len(parts) == 1:

            if not student:
                return HttpResponse("END Not registered", content_type="text/plain")

            if not student.is_ussd_registered:
                return HttpResponse("CON Set 4-digit PIN", content_type="text/plain")

            return HttpResponse("CON Enter PIN", content_type="text/plain")

        # =========================
        # STEP 3: REGISTER OR LOGIN PIN
        # =========================
        if len(parts) == 2:

            if not student:
                return HttpResponse("END Invalid admission number", content_type="text/plain")

            # REGISTER PIN
            if not student.is_ussd_registered:

                if not pin or len(pin) != 4 or not pin.isdigit():
                    return HttpResponse("END PIN must be 4 digits", content_type="text/plain")

                student.pin = make_password(pin)
                student.is_ussd_registered = True
                student.phone = phone or student.phone
                student.save()

                return HttpResponse("END PIN created. Re-dial to vote.", content_type="text/plain")

            # LOGIN WITH PIN
            if not is_authenticated(student, pin):
                return HttpResponse("END Wrong PIN", content_type="text/plain")

            return HttpResponse(
                f"CON Welcome {student.full_name}\n1. Vote",
                content_type="text/plain"
            )

        # =========================
        # STEP 4: SELECT POSITION
        # =========================
        if len(parts) == 3:

            if not is_authenticated(student, pin):
                return HttpResponse("END Authentication failed", content_type="text/plain")

            positions = list(Position.objects.order_by("id"))

            if not positions:
                return HttpResponse("END No positions available", content_type="text/plain")

            msg = "CON Select Position\n"
            for i, p in enumerate(positions, 1):
                msg += f"{i}. {p.name}\n"

            return HttpResponse(msg, content_type="text/plain")

        # =========================
        # STEP 5: SELECT CANDIDATE
        # =========================
        if len(parts) == 4:

            if not is_authenticated(student, pin):
                return HttpResponse("END Authentication failed", content_type="text/plain")

            pos_index = safe_int(parts[2])
            positions = list(Position.objects.order_by("id"))

            if not pos_index or pos_index < 1 or pos_index > len(positions):
                return HttpResponse("END Invalid position", content_type="text/plain")

            position = positions[pos_index - 1]

            candidates = list(Candidate.objects.filter(position=position).order_by("id"))

            if not candidates:
                return HttpResponse("END No candidates found", content_type="text/plain")

            msg = "CON Select Candidate\n"
            for i, c in enumerate(candidates, 1):
                msg += f"{i}. {c.name}\n"

            return HttpResponse(msg, content_type="text/plain")

        # =========================
        # STEP 6: VOTE SUBMISSION
        # =========================
        if len(parts) >= 5:

            if not is_authenticated(student, pin):
                return HttpResponse("END Authentication failed", content_type="text/plain")

            pos_index = safe_int(parts[2])
            cand_index = safe_int(parts[3])

            positions = list(Position.objects.order_by("id"))

            if not pos_index or pos_index < 1 or pos_index > len(positions):
                return HttpResponse("END Invalid position", content_type="text/plain")

            position = positions[pos_index - 1]

            candidates = list(Candidate.objects.filter(position=position).order_by("id"))

            if not cand_index or cand_index < 1 or cand_index > len(candidates):
                return HttpResponse("END Invalid candidate", content_type="text/plain")

            candidate = candidates[cand_index - 1]

            if phone and student.phone != phone:
                student.phone = phone
                student.save(update_fields=["phone"])

            try:
                submit_vote(
                    candidate=candidate,
                    user=student.user,
                    phone=phone,
                    send_notifications=False,
                )
            except VoteSubmissionError as exc:
                return HttpResponse(f"END {str(exc)}", content_type="text/plain")

            send_sms(phone, VOTE_CONFIRMATION_MESSAGE)

            return HttpResponse(f"END Vote recorded for {candidate.name}", content_type="text/plain")

        return HttpResponse("END Invalid request", content_type="text/plain")

    except Exception as e:
        return HttpResponse(f"END ERROR: {str(e)}", content_type="text/plain")
