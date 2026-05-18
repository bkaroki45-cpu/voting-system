from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Q


# =============================
# 1. STUDENT MODEL
# =============================
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=150)
    admission_number = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return f"{self.full_name} ({self.admission_number})"


# =============================
# 2. POSITIONS
# =============================
class Position(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# =============================
# 3. CANDIDATES
# =============================
class Candidate(models.Model):
    position = models.ForeignKey(Position, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    deputy_name = models.CharField(max_length=100, blank=True, null=True)
    photo = models.ImageField(upload_to='candidates/', blank=True, null=True)
    party = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.position.name})"


# =============================
# 4. SCHOOL STUDENT (WEB + USSD)
# =============================
class SchoolStudent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=150)
    admission_number = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)

    imported = models.BooleanField(default=False)

    # 🔐 SHARED PIN (WEB + USSD)
    pin = models.CharField(max_length=255, null=True, blank=True)
    is_ussd_registered = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name} ({self.admission_number})"

    # =============================
    # PIN CHECK (USED BY BOTH WEB & USSD)
    # =============================
    def check_pin(self, raw_pin):
        if not self.pin or not raw_pin:
            return False
        return check_password(raw_pin, self.pin)


# =============================
# 5. VOTING SESSION
# =============================
class VotingSession(models.Model):
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    active = models.BooleanField(default=False)

    def is_open(self):
        now = timezone.now()
        return self.active and self.start_datetime <= now <= self.end_datetime

    # GLOBAL SESSION FETCH
    @staticmethod
    def get_active_session():
        return VotingSession.objects.filter(active=True).first()

    def __str__(self):
        return f"{self.start_datetime} → {self.end_datetime}"


# =============================
# 6. VOTES
# =============================
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
        return f"{self.user or self.phone} voted {self.candidate.name}"

    # =============================
    # GLOBAL DOUBLE VOTE CHECK
    # =============================
    @staticmethod
    def has_voted(user=None, phone=None, position=None):
        if not position:
            return False

        query = Q()

        if user:
            query |= Q(user=user)

        if phone:
            query |= Q(phone=phone)

        if not query:
            return False

        return Vote.objects.filter(query, position=position).exists()


# =============================
# 7. COMMENTS
# =============================
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    adm_number = models.CharField(max_length=20)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.adm_number}"
