# Replaces the first experimental flat job table with a project/task sheet.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('jobgrid', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobGridProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('customer', models.CharField(blank=True, max_length=255)),
                ('job_number', models.CharField(blank=True, max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(db_index=True, default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Project Planning Sheet',
                'verbose_name_plural': 'Project Planning Sheets',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='JobGridTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_name', models.CharField(max_length=255)),
                ('start', models.DateField(blank=True, null=True)),
                ('finish', models.DateField(blank=True, null=True)),
                ('duration', models.CharField(blank=True, max_length=50)),
                ('predecessors', models.CharField(blank=True, max_length=255)),
                ('assigned_to', models.CharField(blank=True, max_length=255)),
                ('percent_complete', models.PositiveSmallIntegerField(default=0)),
                ('status', models.CharField(blank=True, choices=[('Not Started', 'Not Started'), ('In Progress', 'In Progress'), ('Waiting', 'Waiting'), ('Complete', 'Complete'), ('On Hold', 'On Hold')], default='Not Started', max_length=50)),
                ('comments', models.TextField(blank=True)),
                ('is_group', models.BooleanField(default=False)),
                ('is_expanded', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(db_index=True, default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='jobgrid.jobgridtask')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='jobgrid.jobgridproject')),
            ],
            options={
                'verbose_name': 'Project Task',
                'verbose_name_plural': 'Project Tasks',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.DeleteModel(name='JobGridRow'),
    ]
