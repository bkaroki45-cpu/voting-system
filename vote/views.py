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
            # Convert full_name to uppercase to normalize
            full_name_input = form.cleaned_data['full_name'].strip().upper()
            admission_number = form.cleaned_data['admission_number'].strip()
            password = form.cleaned_data['password1']

            # 1. Check school records using uppercase comparison
            try:
                school_student = SchoolStudent.objects.get(
                    full_name__iexact=full_name_input,
                    admission_number=admission_number
                )
            except SchoolStudent.DoesNotExist:
                form.add_error(None, "Details do not match school records.")
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
            names = full_name_input.split()
            first_name = names[0]
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


@login_required
def vote_page(request):
    user = request.user

    # Get the latest active voting session
    try:
        session = VotingSession.objects.filter(active=True).latest('start_time')
    except VotingSession.DoesNotExist:
        session = None

    # Block voting if session is inactive or closed
    if not session or not session.is_open():
        return render(request, 'vote/closed.html', {
            'message': 'Voting is currently closed.',
            'session': session
        })

    # Check if user has already voted
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

    # Combine session date + end_time for countdown
    session_end = None
    if session:
        session_end = timezone.make_aware(
            timezone.datetime.combine(session.date, session.end_time)
        )

    return render(request, 'vote/vote_page.html', {
        'positions': positions,
        'session': session,
        'session_end': session_end  # Pass full datetime to template
    })





@login_required
def results_page(request):
    positions = Position.objects.all()
    results = []

    # Get latest session
    try:
        session = VotingSession.objects.latest('start_time')
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
        # Combine session.date and end_time to a full datetime
        session_end_datetime = timezone.make_aware(
            datetime.combine(session.date, session.end_time)
        )
        session_timestamp = int(session_end_datetime.timestamp() * 1000)  # JS needs ms

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
    try:
        session = VotingSession.objects.latest('start_time')
    except VotingSession.DoesNotExist:
        # No session exists → redirect to results page
        return redirect('results_page')

    # -----------------------------
    # If voting is ongoing → stay on results page
    # -----------------------------
    if session.is_open():
        now = timezone.now()
        session_end_datetime = timezone.make_aware(
            datetime.combine(session.date, session.end_time)
        )
        remaining = session_end_datetime - now
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        seconds = remaining.seconds % 60
        countdown = f"{hours}h {minutes}m {seconds}s remaining"

        return render(request, 'vote/results.html', {
            'results': [],  # optionally hide final results
            'voting_message': "Voting is still ongoing. Final results are not ready.",
            'countdown': countdown,
            'session': session
        })

    # -----------------------------
    # Voting is closed → handle comment submission
    # -----------------------------
    error_message = None
    if request.method == "POST":
        message = request.POST.get('message')
        adm_number = request.POST.get('adm_number')

        # Get logged-in user's admission number
        try:
            user_adm_number = request.user.schoolstudent.admission_number
        except SchoolStudent.DoesNotExist:
            user_adm_number = None

        # Validate inputs
        if not message or not adm_number:
            error_message = "Please fill in all fields."
        elif adm_number != user_adm_number:
            error_message = "Invalid admission number. Please use your own admission number."
        else:
            # Save comment
            Comment.objects.create(user=request.user, adm_number=adm_number, message=message)
            return redirect('final_results_page')  # refresh page

    # -----------------------------
    # Build final results
    # -----------------------------
    positions = Position.objects.all()
    final_results = []

    for position in positions:
        candidates = Candidate.objects.filter(position=position)
        total_votes = Vote.objects.filter(candidate__position=position).count()

        candidate_results = []
        max_votes = 0

        for candidate in candidates:
            vote_count = Vote.objects.filter(candidate=candidate).count()
            percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
            if vote_count > max_votes:
                max_votes = vote_count

            candidate_results.append({
                'id': candidate.id,
                'name': f"{candidate.name} & {candidate.deputy_name}" if candidate.deputy_name else candidate.name,
                'party': candidate.party if candidate.party else '',
                'votes': vote_count,
                'percentage': round(percentage, 1),
                'photo': candidate.photo.url if candidate.photo else None,
            })

        winners = [c for c in candidate_results if c['votes'] == max_votes] if max_votes > 0 else []

        final_results.append({
            'position': position.name,
            'candidates': candidate_results,
            'winners': winners
        })

    # Fetch all comments
    comments = Comment.objects.all().order_by('-timestamp')

    return render(request, 'vote/final_results.html', {
        'final_results': final_results,
        'session': session,
        'comments': comments,
        'error_message': error_message
    })