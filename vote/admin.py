# admin.py
from .models import VotingSession, SchoolStudent, Position, Candidate, Vote, Comment
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from django.db.models import Q
# -----------------------------
# Resource for import/export
# -----------------------------
class SchoolStudentResource(resources.ModelResource):
    """
    Import/Export resource for SchoolStudent.
    Imported students will NOT create User objects.
    """
    def before_import_row(self, row, **kwargs):
        # Mark as imported
        row['imported'] = True

    class Meta:
        model = SchoolStudent
        fields = ('id', 'full_name', 'admission_number', 'imported')
        import_id_fields = ('admission_number',)


# -----------------------------
# Admin for SchoolStudent
# -----------------------------
@admin.register(SchoolStudent)
class SchoolStudentAdmin(ImportExportModelAdmin):
    resource_class = SchoolStudentResource
    list_display = ('full_name', 'admission_number', 'imported')
    search_fields = ('full_name', 'admission_number')


# -----------------------------
# Inline for UserAdmin
# -----------------------------
class SchoolStudentInline(admin.StackedInline):
    model = SchoolStudent
    can_delete = False
    verbose_name_plural = 'School Student'


# -----------------------------
# Custom UserAdmin
# -----------------------------


class UserAdmin(BaseUserAdmin):
    inlines = (SchoolStudentInline,)
    list_display = ('username', 'email', 'get_full_name', 'get_admission_number', 'is_staff', 'is_active')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Show:
        # 1) Staff or superusers (admins)
        # 2) Registered students (schoolstudent.imported=False)
        return qs.filter(
            Q(is_staff=True) | Q(is_superuser=True) | Q(schoolstudent__imported=False)
        )

    def get_full_name(self, obj):
        # Admins may not have linked SchoolStudent
        return obj.schoolstudent.full_name if hasattr(obj, 'schoolstudent') else obj.get_full_name()
    get_full_name.short_description = 'Full Name'

    def get_admission_number(self, obj):
        return obj.schoolstudent.admission_number if hasattr(obj, 'schoolstudent') else '-'
    get_admission_number.short_description = 'Admission Number'


# -----------------------------
# Custom admin action: Reset Election
# -----------------------------
@admin.action(description="Reset Election (delete all positions, candidates, votes, comments, sessions)")
def reset_election(modeladmin, request, queryset):
    Vote.objects.all().delete()
    Comment.objects.all().delete()
    Candidate.objects.all().delete()
    Position.objects.all().delete()
    VotingSession.objects.all().delete()
    messages.success(request, "Election has been reset. All positions, candidates, votes, comments, and sessions cleared.")


# -----------------------------
# VotingSession admin with reset action
# -----------------------------
@admin.register(VotingSession)
class VotingSessionAdmin(admin.ModelAdmin):
    list_display = ('start_time', 'end_time', 'active')
    list_editable = ('active',)
    actions = [reset_election]  # attach reset action here


# -----------------------------
# Re-register User admin
# -----------------------------
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# -----------------------------
# Register other models
# -----------------------------
admin.site.register(Position)
admin.site.register(Candidate)
admin.site.register(Vote)