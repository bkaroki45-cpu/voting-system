from django import forms
from django.contrib.auth.models import User
from .models import Student, SchoolStudent
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm
from .models import VotingSession
from django.utils.timezone import localtime
from datetime import timedelta


class StudentRegisterForm(UserCreationForm):
    admission_number = forms.CharField(
        max_length=50,
        help_text="Enter your exact school admission number."
    )

    class Meta:
        model = User
        fields = ['admission_number', 'password1', 'password2']

    def clean_admission_number(self):
        admission_number = self.cleaned_data.get('admission_number').strip()

        # Check if student exists
        if not SchoolStudent.objects.filter(admission_number=admission_number).exists():
            raise forms.ValidationError("Admission number not found in school records.")

        # Check if already registered
        student = SchoolStudent.objects.get(admission_number=admission_number)
        if student.user is not None:
            raise forms.ValidationError("This student has already registered.")

        return admission_number

    def save(self, commit=True):
        user = super().save(commit=False)

        admission_number = self.cleaned_data['admission_number']
        user.username = admission_number

        if commit:
            user.save()

        # Link to SchoolStudent
        student = SchoolStudent.objects.get(admission_number=admission_number)
        student.user = user
        student.imported = False
        student.save()

        return user
    
    

class StudentLoginForm(AuthenticationForm):
    username = forms.CharField(label="Admission Number")  # this will match User.username


    # forms.py
from django import forms
from .models import VotingSession
from django.utils.timezone import localtime

class VotingSessionForm(forms.ModelForm):
    start_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',  # allows typing manually
                'step': 60,                # minute steps
            },
            format='%Y-%m-%dT%H:%M'       # HTML5 format
        )
    )
    end_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'step': 60,
            },
            format='%Y-%m-%dT%H:%M'
        )
    )

    class Meta:
        model = VotingSession
        fields = ['start_datetime', 'end_datetime', 'active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-fill with current local time (Kenyan)
        if not self.instance.pk:
            now = localtime()
            self.fields['start_datetime'].initial = now.strftime('%Y-%m-%dT%H:%M')
            self.fields['end_datetime'].initial = (now + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
