from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vote", "0005_alter_schoolstudent_pin"),
    ]

    operations = [
        migrations.AddField(
            model_name="schoolstudent",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="schoolstudent",
            name="phone",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
    ]
