from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vote", "0006_schoolstudent_email_schoolstudent_phone"),
    ]

    operations = [
        migrations.AddField(
            model_name="votingsession",
            name="results_email_sent",
            field=models.BooleanField(default=False),
        ),
    ]
