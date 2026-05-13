# admin.py
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from django.db.models import Q
from django.http import HttpResponse
import csv
from django.urls import path
from django.utils.html import format_html

from .models import VotingSession, SchoolStudent, Position, Candidate, Vote, Comment


def build_session_results(session):
    votes = Vote.objects.filter(
        voted_at__gte=session.start_datetime,
        voted_at__lte=session.end_datetime
    ).select_related("candidate", "position")

    votes_by_candidate = {}
    votes_by_position = {}

    for vote in votes:
        votes_by_candidate[vote.candidate_id] = votes_by_candidate.get(vote.candidate_id, 0) + 1
        votes_by_position[vote.position_id] = votes_by_position.get(vote.position_id, 0) + 1

    results = []

    for position in Position.objects.all():
        candidates = Candidate.objects.filter(position=position)
        total_votes = votes_by_position.get(position.id, 0)

        for candidate in candidates:
            vote_count = votes_by_candidate.get(candidate.id, 0)
            percentage = (vote_count / total_votes * 100) if total_votes else 0

            results.append({
                "position": position.name,
                "candidate": candidate.name,
                "party": candidate.party or "",
                "votes": vote_count,
                "percentage": round(percentage, 1),
            })

    return results

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
@admin.action(description="Reset Election")
def reset_election(modeladmin, request, queryset):
    Vote.objects.all().delete()
    Comment.objects.all().delete()
    Candidate.objects.all().delete()
    Position.objects.all().delete()
    VotingSession.objects.all().delete()

    messages.success(request, "Election reset successfully.")


@admin.register(VotingSession)
class VotingSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'export_link')
    actions = [reset_election]

    def export_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank" style="color:#00bcd4; font-weight:bold;">⬇ Export Results</a>',
            f"/admin/{obj._meta.app_label}/votingsession/export-results/{obj.id}/"
        )

    export_link.short_description = "Export Results"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'export-results/<int:session_id>/',
                self.admin_site.admin_view(self.export_results_csv),
                name='export-results',
            ),
        ]
        return custom_urls + urls

    def export_results_csv(self, request, session_id):
        session = VotingSession.objects.get(id=session_id)
        results = build_session_results(session)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="results_session_{session_id}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Position', 'Candidate', 'Party', 'Votes', 'Percentage'])

        for r in results:
            writer.writerow([
                r['position'],
                r['candidate'],
                r['party'],
                r['votes'],
                r['percentage'],
            ])

        return response


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
