from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils.timezone import localtime
from datetime import timedelta
from django.contrib.auth.hashers import make_password

from .models import Student, SchoolStudent, VotingSession


# -----------------------------
# Register Form
# -----------------------------
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

from .models import SchoolStudent


class StudentRegisterForm(UserCreationForm):
    admission_number = forms.CharField(max_length=50)
    pin = forms.CharField(max_length=4)

    class Meta:
        model = User
        fields = ['admission_number', 'password1', 'password2', 'pin']

    def clean_admission_number(self):
        admission_number = self.cleaned_data['admission_number'].strip()

        if not SchoolStudent.objects.filter(admission_number=admission_number).exists():
            raise forms.ValidationError("Admission number not found.")

        student = SchoolStudent.objects.get(admission_number=admission_number)

        if student.user:
            raise forms.ValidationError("Already registered.")

        return admission_number

    def save(self, commit=True):
        user = super().save(commit=False)

        admission_number = self.cleaned_data['admission_number']
        pin = self.cleaned_data['pin']

        user.username = admission_number

        if commit:
            user.save()

        student = SchoolStudent.objects.get(admission_number=admission_number)
        student.user = user
        student.pin = make_password(pin)   # ✅ STORE PIN HERE
        student.is_ussd_registered = True
        student.save()

        return user


# -----------------------------
# Login Form
# -----------------------------
class StudentLoginForm(AuthenticationForm):
    username = forms.CharField(label="Admission Number")


# -----------------------------
# Voting Session Form
# -----------------------------
from django import forms
from django.utils.timezone import localtime
from datetime import timedelta
from .models import VotingSession


class VotingSessionForm(forms.ModelForm):

    start_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'step': 60},
            format='%Y-%m-%dT%H:%M'
        )
    )

    end_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'step': 60},
            format='%Y-%m-%dT%H:%M'
        )
    )

    class Meta:
        model = VotingSession
        fields = ['start_datetime', 'end_datetime', 'active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            now = localtime()

            self.fields['start_datetime'].initial = now.strftime('%Y-%m-%dT%H:%M')
            self.fields['end_datetime'].initial = (
                now + timedelta(hours=1)
            ).strftime('%Y-%m-%dT%H:%M')

    # 🔥 ADD THIS (critical fix)
    def clean(self):
            cleaned_data = super().clean()

            start = cleaned_data.get("start_datetime")
            end = cleaned_data.get("end_datetime")

            if start and end:
                if end <= start:
                    raise forms.ValidationError("End time must be after start time.")

            return cleaned_data
