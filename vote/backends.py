from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from .models import SchoolStudent


class AdmissionNumberBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            student = SchoolStudent.objects.get(admission_number=username)
            user = student.user

            # ✅ Check if user exists first
            if user is not None and user.check_password(password):
                return user

        except SchoolStudent.DoesNotExist:
            return None

        return None