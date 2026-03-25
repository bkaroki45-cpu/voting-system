from django import forms
from django.contrib.auth.models import User
from .models import Student, SchoolStudent
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm


class StudentRegisterForm(UserCreationForm):
    full_name = forms.CharField(max_length=150)
    admission_number = forms.CharField(max_length=50)

    class Meta:
        model = User
        fields = ['full_name', 'admission_number', 'password1', 'password2']

    def clean(self):
        cleaned_data = super().clean()
        full_name = cleaned_data.get('full_name')
        admission_number = cleaned_data.get('admission_number')

        # Check if this student exists in SchoolStudent
        try:
            school_student = SchoolStudent.objects.get(
                full_name=full_name,
                admission_number=admission_number
            )
        except SchoolStudent.DoesNotExist:
            raise forms.ValidationError(
                "Your name or admission number does not match school records."
            )

        # Check if this student already has a linked user
        if school_student.user is not None:
            raise forms.ValidationError("This student has already registered.")

        return cleaned_data

    def save(self, commit=True):
        # Create user instance but don’t save yet
        user = super().save(commit=False)

        # Set username = admission_number (must be unique)
        user.username = self.cleaned_data['admission_number']

        # Save user to DB
        user.save()

        # Link the saved user to the SchoolStudent
        full_name = self.cleaned_data['full_name']
        admission_number = self.cleaned_data['admission_number']

        school_student = SchoolStudent.objects.get(
            full_name=full_name,
            admission_number=admission_number
        )
        school_student.user = user
        school_student.imported = False
        school_student.save()

        return user
    
    

class StudentLoginForm(AuthenticationForm):
    username = forms.CharField(label="Admission Number")  # this will match User.username