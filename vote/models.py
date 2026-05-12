from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password

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
    party = models.CharField(max_length=100, blank=True, null=True)  # NEW FIELD

    def __str__(self):
        position = self.position.name if self.position else "Unknown Position"
    
        if self.deputy_name:
            if self.party:
                return f"{self.name} & {self.deputy_name} ({position}) - {self.party}"
            return f"{self.name} & {self.deputy_name} ({position})"
    
        if self.party:
            return f"{self.name} ({position}) - {self.party}"
    
        return f"{self.name} ({position})"


# -----------------------------
# 4️⃣ Votes
# -----------------------------
class Vote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    phone = models.CharField(max_length=20, null=True, blank=True)

    position = models.ForeignKey(Position, on_delete=models.CASCADE)

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)

    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'position'],
                name='unique_user_position'
            ),
            models.UniqueConstraint(
                fields=['phone', 'position'],
                name='unique_phone_position'
            ),
        ]

    def __str__(self):
        if self.user:
            voter = self.user.username
        elif self.phone:
            voter = self.phone
        else:
            voter = "Unknown"

        return f"{voter} voted for {self.candidate.name}"


# -----------------------------
# 5️⃣ SchoolStudent (imported + registered students)
# -----------------------------
class SchoolStudent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=150)
    admission_number = models.CharField(max_length=50, unique=True)

    imported = models.BooleanField(default=False)

    # 🔥 ADD THESE FOR USSD
    pin = models.CharField(max_length=4, null=True, blank=True)
    is_ussd_registered = models.BooleanField(default=False)
    

    def __str__(self):
        return f"{self.full_name} ({self.admission_number})"
    


from django.db import models
from django.utils import timezone


class VotingSession(models.Model):
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    active = models.BooleanField(default=False)

    def is_open(self):
        now = timezone.now()
        return (
            self.active and
            self.start_datetime <= now <= self.end_datetime
        )

    def __str__(self):
        return f"{self.start_datetime} → {self.end_datetime} | Active: {self.active}"
    
    def clean(self):
        if self.end_datetime <= self.start_datetime:
            raise ValidationError("End must be after start")
        
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    adm_number = models.CharField(max_length=20)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.adm_number}"

