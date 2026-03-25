from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

# -----------------------------
# 1️⃣ Custom Student Model (for manually registered users)
# -----------------------------
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=150)
    admission_number = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return f"{self.full_name} ({self.admission_number})"


# -----------------------------
# 2️⃣ Positions
# -----------------------------
class Position(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# -----------------------------
# 3️⃣ Candidates
# -----------------------------
class Candidate(models.Model):
    position = models.ForeignKey(Position, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    deputy_name = models.CharField(max_length=100, blank=True, null=True)
    photo = models.ImageField(upload_to='candidates/', blank=True, null=True)

    def __str__(self):
        if self.deputy_name:
            return f"{self.name} & {self.deputy_name} ({self.position.name})"
        return f"{self.name} ({self.position.name})"


# -----------------------------
# 4️⃣ Votes
# -----------------------------
class Vote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    position = models.ForeignKey(Position, on_delete=models.CASCADE)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'position')

    def __str__(self):
        return f"{self.user.username} voted for {self.candidate.name} ({self.position.name})"


# -----------------------------
# 5️⃣ SchoolStudent (imported + registered students)
# -----------------------------
class SchoolStudent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=150)
    admission_number = models.CharField(max_length=50, unique=True)
    imported = models.BooleanField(default=False)  # True if imported via CSV

    def __str__(self):
        return f"{self.full_name} ({self.admission_number})"
    


class VotingSession(models.Model):
    date = models.DateField(default=timezone.localdate)  # voting day
    start_time = models.TimeField()  # e.g., 9:30 AM
    end_time = models.TimeField()    # e.g., 3:30 PM
    active = models.BooleanField(default=False)

    def is_open(self):
        now = timezone.localtime()
        if not self.active:
            return False
        # Combine date with start/end time for comparison
        start_dt = timezone.make_aware(
            timezone.datetime.combine(self.date, self.start_time)
        )
        end_dt = timezone.make_aware(
            timezone.datetime.combine(self.date, self.end_time)
        )
        return start_dt <= now <= end_dt

    def __str__(self):
        return f"Voting on {self.date}: {self.start_time} - {self.end_time} | Active: {self.active}"