# admin.py
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from django.db.models import Q

from .models import VotingSession, SchoolStudent, Position, Candidate, Vote, Comment

# -----------------------------
# Resource for import/export SchoolStudent
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
# Admin for SchoolStudent (reference database)
# -----------------------------
@admin.register(SchoolStudent)
class SchoolStudentAdmin(ImportExportModelAdmin):
    resource_class = SchoolStudentResource
    list_display = ('full_name', 'admission_number', 'imported')
    search_fields = ('full_name', 'admission_number')


# -----------------------------
# VotingSession admin with reset action
# -----------------------------
@admin.action(description="Reset Election (delete all positions, candidates, votes, comments, sessions)")
def reset_election(modeladmin, request, queryset):
    Vote.objects.all().delete()
    Comment.objects.all().delete()
    Candidate.objects.all().delete()
    Position.objects.all().delete()
    VotingSession.objects.all().delete()
    messages.success(
        request,
        "Election has been reset. All positions, candidates, votes, comments, and sessions cleared."
    )


@admin.register(VotingSession)
class VotingSessionAdmin(admin.ModelAdmin):
    list_display = ('start_time', 'end_time', 'active')
    list_editable = ('active',)
    actions = [reset_election]


# -----------------------------
# Re-register User admin (default, no SchoolStudent inline)
# -----------------------------
admin.site.unregister(User)
admin.site.register(User, BaseUserAdmin)


# -----------------------------
# Register other models normally
# -----------------------------
admin.site.register(Position)
admin.site.register(Candidate)
admin.site.register(Vote)
admin.site.register(Comment)