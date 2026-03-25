# views.py

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from .forms import StudentRegisterForm
from .models import SchoolStudent, Candidate, Position, Vote
from django.contrib import messages
from django.contrib.auth.models import User

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
            full_name = form.cleaned_data['full_name'].strip()
            admission_number = form.cleaned_data['admission_number'].strip()
            password = form.cleaned_data['password1']

            # Get the matching SchoolStudent (case-insensitive)
            try:
                school_student = SchoolStudent.objects.get(
                    full_name__iexact=full_name,
                    admission_number=admission_number
                )
            except SchoolStudent.DoesNotExist:
                form.add_error(None, "Your details do not match school records.")
                return render(request, 'vote/register.html', {'form': form})

            if school_student.user:
                form.add_error(None, "This student has already registered.")
                return render(request, 'vote/register.html', {'form': form})

            # Create User with unique username = admission_number
            user = User.objects.create_user(
                username=admission_number,
                password=password,
                first_name=full_name.split()[0],
                last_name=" ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else "",
            )

            # Link User to SchoolStudent
            school_student.user = user
            school_student.imported = False
            school_student.save()

            # Authenticate & login
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
        admission_number = request.POST['admission_number']
        password = request.POST['password']

        # Authenticate
        user = authenticate(request, username=admission_number, password=password)

        # Only allow login for manually registered students (imported=False)
        if user is not None:
            try:
                student = user.schoolstudent
                if student.imported:
                    # Imported student cannot login
                    error = "You cannot login. Please register first."
                    return render(request, 'vote/login.html', {'error': error})
            except SchoolStudent.DoesNotExist:
                # No SchoolStudent linked? Just block login
                error = "Invalid user."
                return render(request, 'vote/login.html', {'error': error})

            login(request, user)
            return redirect('vote_page')
        else:
            error = "Invalid admission number or password"
            return render(request, 'vote/login.html', {'error': error})

    return render(request, 'vote/login.html')


# -----------------------------
# Voting page
# -----------------------------
@login_required
def vote_page(request):
    user = request.user

    # Check if user has already voted
    if Vote.objects.filter(user=user).exists():
        # Redirect to results page instead of showing 'already_voted.html'
        return redirect('results_page')

    positions = Position.objects.all()
    candidates = Candidate.objects.all()

    if request.method == "POST":
        # Handle submitted votes
        for position in positions:
            candidate_id = request.POST.get(f'position_{position.id}')
            if candidate_id:
                candidate = candidates.get(id=candidate_id)
                Vote.objects.create(
                    user=user,
                    position=position,
                    candidate=candidate
                )
        # Redirect to results page after voting
        return redirect('results_page')

    # If GET request, render voting page
    return render(request, 'vote/vote_page.html', {
        'positions': positions,
        'candidates': candidates
    })


@login_required
def thank_you(request):
    return render(request, 'vote/thank_you.html')

@login_required
def already_voted(request):
    """
    Display a page telling the user they have already voted.
    """
    return render(request, 'vote/already_voted.html')


@login_required
def results_page(request):
    positions = Position.objects.all()
    results = []

    for position in positions:
        candidates = Candidate.objects.filter(position=position)
        candidate_results = []
        for candidate in candidates:
            vote_count = Vote.objects.filter(candidate=candidate).count()
            candidate_results.append({
                'name': f"{candidate.name} & {candidate.deputy_name}" if candidate.deputy_name else candidate.name,
                'votes': vote_count,
            })
        results.append({
            'position': position.name,
            'candidates': candidate_results
        })

    return render(request, 'vote/results.html', {'results': results})