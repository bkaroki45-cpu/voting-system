# admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import SchoolStudent, Position, Candidate, Vote

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
        # DO NOT create User here
        # Only manually registered students will have a User

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
        # Only show users whose SchoolStudent.imported=False
        return qs.filter(schoolstudent__imported=False)

    def get_full_name(self, obj):
        return obj.schoolstudent.full_name if hasattr(obj, 'schoolstudent') else '-'
    get_full_name.short_description = 'Full Name'

    def get_admission_number(self, obj):
        return obj.schoolstudent.admission_number if hasattr(obj, 'schoolstudent') else '-'
    get_admission_number.short_description = 'Admission Number'


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