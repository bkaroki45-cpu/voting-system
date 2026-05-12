# views.py
from .models import VotingSession
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from .forms import StudentRegisterForm
from .models import SchoolStudent, Candidate, Position, Vote, Comment
from django.contrib import messages
from django.contrib.auth.models import User
from datetime import datetime, date, time
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.contrib.auth.hashers import make_password, check_password
from .models import SchoolStudent

# -----------------------------
# Home page
# -----------------------------
def home(request):
    return render(request, 'vote/home.html')


# -----------------------------
# Student registration
# -----------------------------
def student_register(request):
    if request.method == "POST":
        form = StudentRegisterForm(request.POST)

        if form.is_valid():
            
            admission_number = form.cleaned_data['admission_number'].strip()
            password = form.cleaned_data['password1']

            # 1. Check school records using uppercase comparison
            try:
                school_student = SchoolStudent.objects.get(
                    admission_number=admission_number.strip()
                )
            except SchoolStudent.DoesNotExist:
                form.add_error(None, "Admission number not found in school records.")
                return render(request, 'vote/register.html', {'form': form})

            # 2. If already linked → already registered
            if school_student.user is not None:
                form.add_error(None, "Account already exists. Please login.")
                return render(request, 'vote/register.html', {'form': form})

            # 3. If user exists (even if not linked) → login instead
            if User.objects.filter(username=admission_number).exists():
                form.add_error(None, "Account already exists. Please login.")
                return render(request, 'vote/register.html', {'form': form})

            # 4. Create account (ONLY VALID CASE)
            full_name = school_student.full_name.strip()
            names = full_name.split()
            
            first_name = names[0]
            last_name = " ".join(names[1:]) if len(names) > 1 else ""
            last_name = " ".join(names[1:]) if len(names) > 1 else ""

            user = User.objects.create_user(
                username=admission_number,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )

            # ✅ Make sure user is active so visible in admin
            user.is_active = True

            # ✅ Optional: make user staff so visible in admin Users section
            # user.is_staff = True  # uncomment if you want them to appear immediately in admin

            user.save()

            # 5. Link student → user
            school_student.user = user
            school_student.save()

            # 6. Login
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)

            return redirect('vote_page')

    else:
        form = StudentRegisterForm()

    return render(request, 'vote/register.html', {'form': form})
# -----------------------------
# Student login
# -----------------------------
def student_login(request):
    if request.method == "POST":
        admission_number = request.POST.get('admission_number', '').strip()
        password = request.POST.get('password', '').strip()

        # Check if user exists in the User table
        if not User.objects.filter(username=admission_number).exists():
            # User not registered yet
            error = "You are not registered yet. Please register first."
            return render(request, 'vote/login.html', {'error': error})

        # Authenticate
        user = authenticate(request, username=admission_number, password=password)
        if user is not None:
            # Login the user
            login(request, user)
            return redirect('vote_page')
        else:
            # Wrong password
            error = "Invalid admission number or password."
            return render(request, 'vote/login.html', {'error': error})

    # GET request
    return render(request, 'vote/login.html')





from django.utils import timezone

@login_required
def vote_page(request):
    user = request.user

    session = VotingSession.objects.filter(active=True)\
        .order_by('-start_datetime').first()

    now = timezone.now()
    print("NOW:", now)

    if not session:
        return render(request, 'vote/closed.html', {
            'message': 'No active voting session found.',
            'session': None
        })

    print("START:", session.start_datetime)
    print("END:", session.end_datetime)

    if not session.is_open():
        return render(request, 'vote/closed.html', {
            'message': 'Voting is currently closed.',
            'session': session
        })

    if Vote.objects.filter(user=user).exists():
        return redirect('results_page')

    positions = Position.objects.all()

    if request.method == "POST":
        for position in positions:
            candidate_id = request.POST.get(f'position_{position.id}')
            if candidate_id:
                candidate = Candidate.objects.get(id=candidate_id)
                Vote.objects.create(user=user, position=position, candidate=candidate)
        return redirect('results_page')

    return render(request, 'vote/vote_page.html', {
        'positions': positions,
        'session': session,
        'session_end': session.end_datetime
    })


@login_required
def results_page(request):
    positions = Position.objects.all()
    results = []

    # Get latest session
    try:
        session = VotingSession.objects.latest('start_datetime')
    except VotingSession.DoesNotExist:
        session = None

    for position in positions:
        candidates = Candidate.objects.filter(position=position)
        total_votes = Vote.objects.filter(candidate__position=position).count()

        candidate_results = []
        for candidate in candidates:
            vote_count = Vote.objects.filter(candidate=candidate).count()
            percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0

            candidate_results.append({
                'name': f"{candidate.name} & {candidate.deputy_name}" if candidate.deputy_name else candidate.name,
                'party': candidate.party if candidate.party else '',
                'votes': vote_count,
                'percentage': round(percentage, 1),
                'photo': candidate.photo.url if candidate.photo else None
            })

        results.append({
            'position': position.name,
            'candidates': candidate_results
        })

    # ✅ Countdown timestamp
    session_timestamp = None
    session_end_datetime = None
    if session:
        session_end_datetime = session.end_datetime
        session_timestamp = int(session_end_datetime.timestamp() * 1000)

    return render(request, 'vote/results.html', {
        'results': results,
        'session': session,
        'session_end': session_end_datetime,
        'session_timestamp': session_timestamp
    })



def close(request):
    return render(request, 'vote/closed.html')

@login_required
def final_results_page(request):

    # -----------------------------
    # Get latest session safely
    # -----------------------------
    session = VotingSession.objects.order_by('-start_datetime').first()

    if not session:
        return redirect('results_page')

    # -----------------------------
    # If voting still open → show message
    # -----------------------------
    if session.is_open():
        return render(request, 'vote/results.html', {
            'voting_message': "Voting is still ongoing. Final results are not ready.",
            'session': session
        })

    # -----------------------------
    # Handle comments
    # -----------------------------
    error_message = None

    if request.method == "POST":
        message = request.POST.get('message')
        adm_number = request.POST.get('adm_number')

        try:
            user_adm_number = request.user.schoolstudent.admission_number
        except:
            user_adm_number = None

        if not message or not adm_number:
            error_message = "Please fill all fields."
        elif adm_number != user_adm_number:
            error_message = "Invalid admission number."
        else:
            Comment.objects.create(
                user=request.user,
                adm_number=adm_number,
                message=message
            )
            return redirect('final_results_page')

    # -----------------------------
    # BUILD RESULTS (FIXED LOGIC)
    # -----------------------------
    final_results = []

    for position in Position.objects.all():

        candidates = Candidate.objects.filter(position=position)

        candidate_results = []

        max_votes = 0

        for candidate in candidates:
            vote_count = Vote.objects.filter(candidate=candidate).count()

            max_votes = max(max_votes, vote_count)

            total_votes = Vote.objects.filter(candidate__position=position).count()

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

        final_results.append({
            "position": position.name,
            "candidates": candidate_results,
            "winners": winners
        })

    comments = Comment.objects.all().order_by('-timestamp')

    return render(request, 'vote/final_results.html', {
        "final_results": final_results,
        "comments": comments,
        "error_message": error_message,
        "session": session
    })






from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.db import connection
from .models import SchoolStudent, Position, Candidate, Vote
from django.contrib.auth.hashers import make_password, check_password


@csrf_exempt
def ussd_callback(request):

    try:
        text = request.POST.get('text', '').strip()
        phone = request.POST.get('phoneNumber', '')

        parts = text.split("*") if text else []

        # =========================
        # STEP 1: ENTER ADMISSION
        # =========================
        if text == "":
            return HttpResponse("CON Enter Admission Number", content_type="text/plain")

        adm = parts[0] if len(parts) > 0 else None
        pin = parts[1] if len(parts) > 1 else None

        student = SchoolStudent.objects.filter(admission_number=adm).first()

        # =========================
        # STEP 2: CHECK STUDENT
        # =========================
        if len(parts) == 1:

            if not student:
                return HttpResponse("END Not registered in school system", content_type="text/plain")

            if not student.is_ussd_registered:
                return HttpResponse("CON Set 4-digit PIN", content_type="text/plain")

            return HttpResponse("CON Enter PIN", content_type="text/plain")

        # =========================
        # STEP 3: REGISTER / LOGIN
        # =========================
        if len(parts) == 2:

            if not student:
                return HttpResponse("END Invalid admission number", content_type="text/plain")

            if not student.is_ussd_registered:
                if len(pin) != 4 or not pin.isdigit():
                    return HttpResponse("END PIN must be 4 digits", content_type="text/plain")

                student.pin = make_password(pin)
                student.is_ussd_registered = True
                student.save()

                return HttpResponse("END PIN created. Dial again.", content_type="text/plain")

            if not check_password(pin, student.pin):
                return HttpResponse("END Wrong PIN", content_type="text/plain")

            return HttpResponse(f"CON Welcome {student.full_name}\n1. Vote", content_type="text/plain")

        # =========================
        # STEP 4: POSITIONS
        # =========================
        if len(parts) == 3:

            if not student or not check_password(pin, student.pin):
                return HttpResponse("END Auth failed", content_type="text/plain")

            positions = Position.objects.all().order_by("id")

            msg = "CON Select Position\n"
            for i, p in enumerate(positions, 1):
                msg += f"{i}. {p.name}\n"

            return HttpResponse(msg, content_type="text/plain")

        # =========================
        # STEP 5: CANDIDATES
        # =========================
        if len(parts) == 4:

            pos_index = int(parts[2])

            positions = list(Position.objects.all().order_by("id"))

            if pos_index < 1 or pos_index > len(positions):
                return HttpResponse("END Invalid position", content_type="text/plain")

            position = positions[pos_index - 1]

            candidates = list(Candidate.objects.filter(position=position).order_by("id"))

            msg = "CON Select Candidate\n"
            for i, c in enumerate(candidates, 1):
                msg += f"{i}. {c.name}\n"

            return HttpResponse(msg, content_type="text/plain")

        # =========================
        # STEP 6: VOTE
        # =========================
        if len(parts) >= 5:

            pos_index = int(parts[2])
            cand_index = int(parts[3])

            positions = list(Position.objects.all().order_by("id"))

            if pos_index < 1 or pos_index > len(positions):
                return HttpResponse("END Invalid position", content_type="text/plain")

            position = positions[pos_index - 1]

            candidates = list(Candidate.objects.filter(position=position).order_by("id"))

            if cand_index < 1 or cand_index > len(candidates):
                return HttpResponse("END Invalid candidate", content_type="text/plain")

            candidate = candidates[cand_index - 1]

            if Vote.objects.filter(phone=phone, position=position).exists():
                return HttpResponse("END Already voted", content_type="text/plain")

            Vote.objects.create(
                user=student.user,
                phone=phone,
                position=position,
                candidate=candidate
            )

            return HttpResponse(f"END Vote submitted for {candidate.name}", content_type="text/plain")

        return HttpResponse("END Invalid request", content_type="text/plain")

    except Exception as e:
        print("USSD ERROR:", e)
        return HttpResponse("END System error. Try again.", content_type="text/plain")